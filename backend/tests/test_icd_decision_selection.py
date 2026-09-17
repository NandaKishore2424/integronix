"""
Unit tests for how agents/icd_decision.py turns candidates into a claim's
ICD code list.

  A  the ICD-10-CM "with" convention: diabetes + CKD -> E1x.22 + N18.x, the
     stage read only from the text, never on the ICD-11 path;
  B  a secondary code must document what distinguishes it (no retinopathy
     code on a CKD note, no type 1 code on a type 2 note);
  C  every extracted diagnosis is resolved, not only diagnoses[0].

No network: the icd_codes lookup, text search and vector search are stubbed.
"""

import pytest

import agents.icd_decision as decision
from agents.icd_decision import _diabetes_ckd_plan, icd_decision_node


def _row(code, description, **extra):
    return {"code": code, "description": description, "is_billable": True,
            "is_cc": False, "is_mcc": False, "base_reimbursement": 0.0,
            "version": "ICD-10-CM-2024", **extra}


ICD_ROWS = {r["code"]: r for r in [
    _row("E10.22", "Type 1 diabetes mellitus with diabetic chronic kidney disease"),
    _row("E11.22", "Type 2 diabetes mellitus with diabetic chronic kidney disease",
         is_cc=True, base_reimbursement=2100.0),
    _row("N18.1", "Chronic kidney disease, stage 1"),
    _row("N18.2", "Chronic kidney disease, stage 2 (mild)"),
    _row("N18.30", "Chronic kidney disease, stage 3 unspecified"),
    _row("N18.31", "Chronic kidney disease, stage 3a"),
    _row("N18.32", "Chronic kidney disease, stage 3b"),
    _row("N18.4", "Chronic kidney disease, stage 4 (severe)"),
    _row("N18.5", "Chronic kidney disease, stage 5"),
    _row("N18.6", "End stage renal disease"),
    _row("N18.9", "Chronic kidney disease, unspecified"),
]}


def _cand(code, description, confidence=0.85, **extra):
    return {"code": code, "description": description, "is_billable": True,
            "is_cc": False, "is_mcc": False, "base_reimbursement": 0.0,
            "icd_version": "ICD-10-CM-2024", "mapping_type": "approximate",
            "confidence": confidence, "source": "embedding", **extra}


E11_9 = _cand("E11.9", "Type 2 diabetes mellitus without complications", 0.9)
E11_331 = _cand("E11.331", "Type 2 diabetes mellitus with moderate nonproliferative "
                           "diabetic retinopathy with macular edema", 0.9)
E11_42 = _cand("E11.42", "Type 2 diabetes mellitus with diabetic polyneuropathy", 0.9)
E10_42 = _cand("E10.42", "Type 1 diabetes mellitus with diabetic polyneuropathy", 0.88)
E13_42 = _cand("E13.42", "Other specified diabetes mellitus with diabetic polyneuropathy", 0.87)
J18_9 = _cand("J18.9", "Pneumonia, unspecified organism")
I10 = _cand("I10", "Essential (primary) hypertension", 0.9)


def _dx(*texts):
    return {"diagnoses": [{"text": t, "evidence_text": t} for t in texts]}


@pytest.fixture
def stubs(monkeypatch):
    """Stub every lookup the node makes. Records what was searched."""
    calls = {"select": [], "text": [], "vector": [], "text_results": {}}

    async def fake_select(table, query="*", filters=None, limit=None):
        calls["select"].append(filters)
        codes = filters["code"][len("in.("):-1].split(",")
        return [ICD_ROWS[c] for c in codes if c in ICD_ROWS]

    async def fake_text(query, org_id, limit=10):
        calls["text"].append(query)
        return calls["text_results"].get(query, [])

    async def fake_vector(text, session_id=""):
        calls["vector"].append(text)
        return []

    monkeypatch.setattr(decision, "select", fake_select)
    monkeypatch.setattr(decision, "get_icd_results", fake_text)
    monkeypatch.setattr(decision, "find_icd_candidates_by_vector", fake_vector)
    return calls


async def _run(entities, candidates, raw_text="", **state):
    out = await icd_decision_node({
        "session_id": "test", "org_id": "org", "raw_text": raw_text,
        "structured_entities": entities, "candidate_icd_codes": list(candidates),
        "mapping_path": "embedding", **state,
    })
    assert not out.get("error_at"), out.get("error_detail")
    return out


def _codes(state):
    return [c["code"] for c in state["icd_codes"]]


# ── A: the "with" convention ────────────────────────────────────────────────

class TestDiabetesCkdPlan:
    @pytest.mark.parametrize("ckd_text,expected", [
        ("Chronic kidney disease stage 1", "N18.1"),
        ("CKD stage 2", "N18.2"),
        ("Chronic kidney disease stage 3", "N18.30"),
        ("CKD stage 3a", "N18.31"),
        ("CKD 3b", "N18.32"),
        ("CKD stage IIIb", "N18.32"),
        ("Chronic kidney disease, stage 4", "N18.4"),
        ("CKD stage 5", "N18.5"),
        ("CKD stage 5 on hemodialysis", "N18.6"),
        ("End-stage renal disease", "N18.6"),
        ("ESRD", "N18.6"),
        ("Chronic kidney disease", "N18.9"),
    ])
    def test_stage_code_comes_from_the_text(self, ckd_text, expected):
        plan, reason = _diabetes_ckd_plan(_dx("Type 2 diabetes mellitus", ckd_text), "")
        assert reason == "applied"
        assert plan["combination_code"] == "E11.22"
        assert plan["stage_code"] == expected

    def test_stage_is_never_inferred_from_egfr(self):
        plan, _ = _diabetes_ckd_plan(
            _dx("Type 2 diabetes mellitus", "Chronic kidney disease"),
            "Type 2 diabetes with chronic kidney disease. eGFR 38 mL/min.",
        )
        assert plan["stage_code"] == "N18.9"
        assert plan["stage_source"] == "not_documented"

    def test_stage_written_elsewhere_in_the_note_is_used(self):
        plan, _ = _diabetes_ckd_plan(
            _dx("Type 2 diabetes mellitus", "Chronic kidney disease"),
            "Known CKD stage 4, followed by nephrology.",
        )
        assert plan["stage_code"] == "N18.4"
        assert plan["stage_source"] == "note"

    def test_conflicting_stages_fall_back_to_unspecified(self):
        plan, _ = _diabetes_ckd_plan(_dx("Type 2 DM", "CKD stage 3a", "CKD stage 4"), "")
        assert plan["stage_code"] == "N18.9"
        assert plan["stage_source"] == "conflicting"

    def test_type_1(self):
        plan, _ = _diabetes_ckd_plan(_dx("Type 1 diabetes mellitus", "CKD stage 2"), "")
        assert plan["combination_code"] == "E10.22"

    def test_undocumented_type_defaults_to_type_2(self):
        plan, _ = _diabetes_ckd_plan(_dx("Diabetes mellitus", "CKD stage 2"), "")
        assert plan["combination_code"] == "E11.22"

    @pytest.mark.parametrize("entities,raw,reason", [
        (_dx("Type 2 diabetes mellitus"), "", "not_documented"),
        (_dx("Type 2 diabetes mellitus", "No evidence of chronic kidney disease"), "", "not_documented"),
        (_dx("Type 2 diabetes mellitus", "CKD stage 3"), "No chronic kidney disease.", "kidney_disease_denied"),
        (_dx("Type 2 diabetes mellitus", "CKD stage 3"), "No evidence of renal disease.", "kidney_disease_denied"),
        (_dx("Type 2 diabetes mellitus without complications", "CKD stage 3"), "", "documentation_conflict"),
        (_dx("Type 2 diabetes mellitus", "CKD stage 3, not due to diabetes"), "", "documented_as_unrelated"),
        (_dx("Gestational diabetes", "CKD stage 3"), "", "diabetes_type_not_supported"),
        (_dx("Type 1 and type 2 diabetes", "CKD stage 3"), "", "diabetes_type_conflict"),
    ])
    def test_rule_stands_aside(self, entities, raw, reason):
        plan, why = _diabetes_ckd_plan(entities, raw)
        assert plan is None
        assert why == reason

    def test_an_unrelated_kidney_denial_does_not_block_the_rule(self):
        """'No acute kidney injury' says nothing about the documented CKD."""
        plan, reason = _diabetes_ckd_plan(
            _dx("Type 2 diabetes mellitus", "CKD stage 3"),
            "Type 2 diabetes with CKD stage 3. No acute kidney injury.",
        )
        assert reason == "applied"
        assert plan["stage_code"] == "N18.30"


class TestConventionInTheNode:
    CKD_NOTE = ("Patient has Type 2 diabetes mellitus with chronic kidney disease "
                "stage 3. eGFR is 42 mL/min.")
    CKD_ENTITIES = _dx("Type 2 diabetes mellitus", "chronic kidney disease stage 3")

    @pytest.mark.asyncio
    async def test_diabetes_and_ckd_code_as_combination_plus_stage(self, stubs):
        out = await _run(self.CKD_ENTITIES, [E11_9, E11_331], self.CKD_NOTE)
        assert _codes(out) == ["E11.22", "N18.30"]
        assert out["final_icd_code"] == "E11.22"
        assert [c["role"] for c in out["icd_codes"]] == ["primary", "additional"]
        trace = out["decision_trace"]
        assert trace["convention"]["applied"] is True
        assert trace["suppressed_codes"] == ["E11.9"]
        # Both lines are coded by the convention: no extra lookup.
        assert stubs["vector"] == []

    @pytest.mark.asyncio
    async def test_icd11_path_never_applies_the_convention(self, stubs):
        who = {**E11_9, "code": "5A11", "icd_version": "ICD-11", "source": "who_icd_api"}
        out = await _run(self.CKD_ENTITIES, [who], self.CKD_NOTE, mapping_path="who_api_icd11")
        assert out["decision_trace"]["convention"] == {
            "rule": "diabetes_ckd", "applied": False, "reason": "icd11_path"}
        assert stubs["select"] == []
        assert "E11.22" not in _codes(out)
        assert stubs["vector"] == [], "no ICD-10-CM vector search on the ICD-11 path"

    @pytest.mark.asyncio
    async def test_complications_ruled_out_stays_e11_9(self, stubs):
        out = await _run(
            _dx("Type 2 diabetes mellitus without complications"),
            [E11_9, E11_331],
            "Type 2 diabetes mellitus without complications. No evidence of renal disease.",
        )
        assert _codes(out) == ["E11.9"]
        assert stubs["select"] == []

    @pytest.mark.asyncio
    async def test_missing_convention_code_fails_the_node(self, stubs, monkeypatch):
        """Never fall back to 'without complications' when the codes are missing."""
        async def empty_select(table, query="*", filters=None, limit=None):
            return []
        monkeypatch.setattr(decision, "select", empty_select)
        out = await icd_decision_node({
            "session_id": "t", "org_id": "org", "raw_text": self.CKD_NOTE,
            "structured_entities": self.CKD_ENTITIES, "candidate_icd_codes": [E11_9],
            "mapping_path": "embedding",
        })
        assert out["error_at"] == "icd_decision"


# ── B: secondary codes must be documented ───────────────────────────────────

class TestDocumentedSecondaries:
    @pytest.mark.asyncio
    async def test_other_diabetes_types_are_not_added(self, stubs):
        """The E11.42 note used to come back as E11.42 + E10.42 + E13.42."""
        out = await _run(
            _dx("Type 2 diabetes mellitus with diabetic polyneuropathy"),
            [E11_42, E10_42, E13_42],
        )
        assert _codes(out) == ["E11.42"]
        rejected = {r["code"]: r["reason"] for r in out["decision_trace"]["rejected"]}
        assert rejected == {"E10.42": "undocumented_detail", "E13.42": "alternative_code"}

    @pytest.mark.asyncio
    async def test_undocumented_retinopathy_is_not_added(self, stubs):
        out = await _run(_dx("Type 2 diabetes mellitus"), [E11_9, E11_331])
        assert _codes(out) == ["E11.9"]
        missing = out["decision_trace"]["rejected"][0]["missing"]
        assert "retinopathy" in missing

    @pytest.mark.asyncio
    async def test_polyneuropathy_and_ckd_note(self, stubs):
        """Sample 02: E11.42 for the first line, E11.22 + N18.32 for the second."""
        out = await _run(
            _dx("Type 2 diabetes mellitus with diabetic polyneuropathy",
                "Type 2 diabetes mellitus with diabetic chronic kidney disease, stage 3b"),
            [E11_42, E10_42, E13_42],
            "eGFR 38 mL/min.",
        )
        assert _codes(out) == ["E11.42", "E11.22", "N18.32"]
        assert out["decision_trace"]["convention"]["covers"] == [1]


# ── C: every diagnosis is resolved ──────────────────────────────────────────

class TestEveryDiagnosis:
    @pytest.mark.asyncio
    async def test_second_diagnosis_is_looked_up_and_coded(self, stubs):
        stubs["text_results"]["Essential hypertension"] = [
            {"code": "I10", "description": "Essential (primary) hypertension", "score": 0.9,
             "is_billable": True, "source": "ICD-10"},
            {"code": "K76.6", "description": "Portal hypertension", "score": 0.72,
             "is_billable": True, "source": "ICD-10"},
        ]
        out = await _run(_dx("Community-acquired pneumonia", "Essential hypertension"), [J18_9])
        assert stubs["text"][-1] == "Essential hypertension"
        assert _codes(out) == ["J18.9", "I10"]
        assert out["icd_codes"][1]["role"] == "secondary"
        assert stubs["vector"] == [], "a fully documented text result needs no vector search"

    @pytest.mark.asyncio
    async def test_vector_search_runs_when_text_search_finds_nothing(self, stubs):
        out = await _run(_dx("Community-acquired pneumonia", "Essential hypertension"), [J18_9])
        assert stubs["vector"] == ["Essential hypertension"]
        assert out["decision_trace"]["line_status"] == {"1": "no_candidates"}
        assert _codes(out) == ["J18.9"]

    @pytest.mark.asyncio
    async def test_negated_and_repeated_lines_are_not_looked_up(self, stubs):
        out = await _run(
            _dx("Community-acquired pneumonia", "No evidence of sepsis", "Community-acquired pneumonia"),
            [J18_9],
        )
        assert stubs["text"] == ["Community-acquired pneumonia"]   # the augmentation for line 0 only
        assert stubs["vector"] == []
        assert out["decision_trace"]["line_status"] == {"1": "negated", "2": "duplicate"}
