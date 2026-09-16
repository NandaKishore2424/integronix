"""
Unit tests for the audit comparison node: the AI's code against the code a
human coder entered.

Regression context: this node used to read an `icd_evidence` table that no
migration ever created. Every run with a human code failed here with a 404,
and no test noticed, because the fake data layer answers any table name and
no test exercised the human-code path.
"""

import asyncio

from agents.audit_comparison import NO_EVIDENCE, audit_comparison_node, documented_evidence


def run(coro):
    return asyncio.run(coro)


E11_9 = {
    "code": "E11.9",
    "description": "Type 2 diabetes mellitus without complications",
    "base_reimbursement": 1200.0,
    "is_cc": False,
    "is_mcc": False,
}
E11_22 = {
    "code": "E11.22",
    "description": "Type 2 diabetes mellitus with diabetic chronic kidney disease",
    "base_reimbursement": 1850.0,
    "is_cc": True,
    "is_mcc": False,
}


def _state(final_code, human_code, **extra):
    return {
        "session_id": "s1",
        "final_icd_code": final_code,
        "human_icd_code": human_code,
        "structured_entities": {
            "diagnoses": [
                {
                    "text": "Type 2 diabetes mellitus",
                    "evidence_text": "Patient has Type 2 diabetes mellitus with chronic kidney disease stage 3.",
                },
                {"text": "Chronic kidney disease stage 3", "evidence_text": "eGFR is 42 mL/min."},
            ]
        },
        "icd_codes": [{"code": final_code}],
        **extra,
    }


class TestHumanCodeComparison:
    def test_exact_match_completes_with_documented_evidence(self, fake_db):
        fake_db.on("select_one", E11_9, E11_9)
        state = run(audit_comparison_node(_state("E11.9", "E11.9")))

        assert state.get("error_at") is None
        assert state["discrepancy_type"] == "EXACT_MATCH"
        assert "chronic kidney disease" in state["discrepancy"]["ai_evidence"]
        assert state["discrepancy"]["human_evidence"] == state["discrepancy"]["ai_evidence"]

    def test_only_the_code_table_is_queried(self, fake_db):
        """Evidence comes from the chart, not from a lookup table."""
        fake_db.on("select_one", E11_22, E11_9)
        run(audit_comparison_node(_state("E11.22", "E11.9")))

        assert {call[1] for call in fake_db.calls} == {"icd_codes"}

    def test_specificity_improvement_carries_revenue_and_cc_flag(self, fake_db):
        fake_db.on("select_one", E11_22, E11_9)
        state = run(audit_comparison_node(_state("E11.22", "E11.9")))

        assert state["discrepancy_type"] == "SPECIFICITY_IMPROVEMENT"
        assert state["financial_delta"] == 650.0
        assert state["drg_flag"] == "CC_MISSED"

    def test_human_code_the_chart_does_not_support_gets_no_evidence(self, fake_db):
        fake_db.on("select_one", E11_22, E11_9)
        state = run(audit_comparison_node(_state("E11.22", "E11.9")))

        assert state["discrepancy"]["human_evidence"] == NO_EVIDENCE
        assert state["discrepancy"]["ai_evidence"] != NO_EVIDENCE

    def test_human_code_among_the_candidates_shares_the_evidence(self, fake_db):
        fake_db.on("select_one", E11_22, E11_9)
        state = run(audit_comparison_node(
            _state("E11.22", "E11.9", candidate_icd_codes=[{"code": "E11.9"}])
        ))

        assert state["discrepancy"]["human_evidence"] == state["discrepancy"]["ai_evidence"]

    def test_without_a_human_code_the_audit_is_skipped(self, fake_db):
        state = run(audit_comparison_node(_state("E11.9", None)))

        assert state["discrepancy_type"] == "NO_COMPARISON"
        assert not fake_db.calls


class TestDocumentedEvidence:
    def test_quotes_are_deduplicated_and_joined(self):
        state = {"structured_entities": {"diagnoses": [
            {"evidence_text": "A."}, {"evidence_text": "A."}, {"evidence_text": " B. "},
        ]}}
        assert documented_evidence(state) == "A. … B."

    def test_missing_or_empty_quotes_say_so(self):
        assert documented_evidence({}) == NO_EVIDENCE
        assert documented_evidence(
            {"structured_entities": {"diagnoses": [{"evidence_text": ""}]}}
        ) == NO_EVIDENCE

    def test_long_evidence_is_capped(self):
        state = {"structured_entities": {"diagnoses": [{"evidence_text": "x" * 2000}]}}
        assert len(documented_evidence(state)) == 500
