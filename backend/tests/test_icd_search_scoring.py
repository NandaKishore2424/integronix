"""
Unit tests for the keyword search scoring in services/icd_service.py.

This is the last-resort path: it runs when the WHO API, the SNOMED crosswalk
and vector search have all produced nothing. Precisely because it is the
fallback, it is the one most likely to hand back a confident wrong answer —
so what it must do well is decline.

The incident these tests encode: a textbook pneumonia note was billed as
S30.810, "Abrasion of lower back and pelvis". The note said "right lower lobe";
the single token "lower" substring-matched "lower back"; and every index hit
scored a flat 0.8 regardless of how little of the query it covered. The
scoring function then faithfully ranked the garbage.
"""

import pytest

import services.icd_service as icd_service
from services.icd_service import (
    MIN_KEYWORD_SCORE,
    _normalize_query,
    query_tokens,
    search_icd_by_text,
)


@pytest.fixture
def stub_index(monkeypatch):
    """
    Substitute the two database helpers so the SCORING is under test rather
    than PostgREST. Returns a setter for the rows the index should yield.
    """
    state = {"index_rows": [], "icd_rows": [], "fallback_rows": []}

    async def fake_search_index_terms(normalized, tokens):
        return state["index_rows"]

    async def fake_search_index_terms_all(tokens):
        # Mirrors the PostgREST `and` of ilikes: a row must contain every token.
        return [
            r for r in state["index_rows"]
            if all(t in (r.get("normalized_term") or "") for t in tokens)
        ]

    async def fake_fetch_codes(codes):
        return [r for r in state["icd_rows"] if r["code"] in set(codes)]

    async def fake_select(table, query="*", filters=None, limit=None):
        return state["fallback_rows"]

    monkeypatch.setattr(icd_service, "_search_index_terms", fake_search_index_terms)
    monkeypatch.setattr(icd_service, "_search_index_terms_all", fake_search_index_terms_all)
    monkeypatch.setattr(icd_service, "_fetch_icd_codes_by_codes", fake_fetch_codes)
    monkeypatch.setattr(icd_service, "select", fake_select)
    return state


PNEUMONIA_QUERY = "Community-acquired pneumonia, right lower lobe"

ABRASION_ROW = {
    "code": "S30.810", "description": "Abrasion of lower back and pelvis",
    "is_billable": True, "is_cc": False, "is_mcc": False, "base_reimbursement": 0.0,
}
PNEUMONIA_ROW = {
    "code": "J18.9", "description": "Pneumonia, unspecified organism",
    "is_billable": True, "is_cc": False, "is_mcc": False, "base_reimbursement": 0.0,
}


class TestAbrasionRegression:
    @pytest.mark.asyncio
    async def test_single_incidental_token_match_is_rejected(self, stub_index):
        """
        "lower back" shares exactly one token ("lower") with a six-token query.
        Coverage scoring puts that at 0.8 * 1/6 = 0.133, far below the floor,
        so it is dropped instead of billed.
        """
        stub_index["index_rows"] = [
            {"code": "S30.810", "normalized_term": "abrasion of lower back and pelvis",
             "term": "abrasion of lower back"},
        ]
        stub_index["icd_rows"] = [ABRASION_ROW]

        results = await search_icd_by_text(PNEUMONIA_QUERY)
        assert [r["code"] for r in results] == [], (
            "an incidental one-token match must not become a billable candidate"
        )

    @pytest.mark.asyncio
    async def test_genuine_match_still_wins(self, stub_index):
        """Rejecting noise must not also reject signal."""
        stub_index["index_rows"] = [
            {"code": "J18.9", "normalized_term": "pneumonia", "term": "pneumonia"},
            {"code": "S30.810", "normalized_term": "abrasion of lower back and pelvis",
             "term": "abrasion of lower back"},
        ]
        stub_index["icd_rows"] = [PNEUMONIA_ROW, ABRASION_ROW]

        results = await search_icd_by_text("pneumonia")
        codes = [r["code"] for r in results]
        assert "J18.9" in codes
        assert "S30.810" not in codes

    @pytest.mark.asyncio
    async def test_returning_nothing_is_an_acceptable_answer(self, stub_index):
        """
        The pipeline treats an empty candidate list as UNKNOWN and refuses to
        bill it. Silence is a valid — and safe — outcome for this path.
        """
        stub_index["index_rows"] = []
        stub_index["fallback_rows"] = []
        assert await search_icd_by_text("something with no matches at all") == []


class TestCoverageScoring:
    @pytest.mark.asyncio
    async def test_exact_term_scores_highest(self, stub_index):
        stub_index["index_rows"] = [
            {"code": "J18.9", "normalized_term": "pneumonia", "term": "pneumonia"},
        ]
        stub_index["icd_rows"] = [PNEUMONIA_ROW]
        results = await search_icd_by_text("pneumonia")
        assert results[0]["score"] == 1.0

    @pytest.mark.asyncio
    async def test_partial_coverage_scores_between_floor_and_one(self, stub_index):
        stub_index["index_rows"] = [
            {"code": "J18.9", "normalized_term": "acute pneumonia unspecified organism",
             "term": "acute pneumonia"},
        ]
        stub_index["icd_rows"] = [PNEUMONIA_ROW]
        results = await search_icd_by_text("acute pneumonia organism")
        assert results, "3-of-3 tokens covered should clear the floor"
        assert MIN_KEYWORD_SCORE <= results[0]["score"] <= 1.0

    @pytest.mark.asyncio
    async def test_scores_below_the_floor_are_dropped(self, stub_index):
        # 1 of 5 tokens -> 0.8 * 0.2 = 0.16
        stub_index["index_rows"] = [
            {"code": "S30.810", "normalized_term": "pelvis", "term": "pelvis"},
        ]
        stub_index["icd_rows"] = [ABRASION_ROW]
        assert await search_icd_by_text("chronic obstructive pulmonary disease pelvis") == []

    def test_floor_is_high_enough_to_reject_one_of_six(self):
        """Guards the constant itself: 0.8 * 1/6 must sit below the floor."""
        assert 0.8 * (1 / 6) < MIN_KEYWORD_SCORE

    def test_effective_coverage_threshold_is_deliberately_strict(self):
        """
        Pins the real bar: score = 0.8 * coverage against a 0.45 floor means a
        partial match needs >56% of the query's tokens. Half coverage (0.40)
        is REJECTED.

        This is strict on purpose. The path only runs after the WHO API, the
        SNOMED crosswalk and vector search have all failed, and its empty
        result becomes UNKNOWN, which the pipeline refuses to bill and routes
        to a human. On this path a false negative costs a review; a false
        positive bills a patient for the wrong condition.
        """
        assert 0.8 * 0.50 < MIN_KEYWORD_SCORE, "half coverage is rejected"
        assert 0.8 * 0.5625 >= MIN_KEYWORD_SCORE, "just over 9/16 coverage is admitted"
        assert 0.8 * 0.75 >= MIN_KEYWORD_SCORE, "three quarters coverage is admitted"


class TestQueryNormalisation:
    @pytest.mark.parametrize("raw,expected", [
        ("Community-acquired pneumonia", "community acquired pneumonia"),
        ("  MULTIPLE   SPACES  ", "multiple spaces"),
        ("Type 2 diabetes (E11.9)", "type 2 diabetes e11 9"),
        ("", ""),
    ])
    def test_normalisation(self, raw, expected):
        assert _normalize_query(raw) == expected

    @pytest.mark.asyncio
    async def test_blank_query_short_circuits(self, stub_index):
        assert await search_icd_by_text("") == []
        assert await search_icd_by_text("   ") == []


def _code_row(code, description):
    return {"code": code, "description": description, "is_billable": True,
            "is_cc": False, "is_mcc": False, "base_reimbursement": 0.0}


E11_9_ROW = _code_row("E11.9", "Type 2 diabetes mellitus without complications")
E11_36_ROW = _code_row("E11.36", "Type 2 diabetes mellitus with diabetic cataract")
E10_9_ROW = _code_row("E10.9", "Type 1 diabetes mellitus without complications")
E11_331_ROW = _code_row(
    "E11.331",
    "Type 2 diabetes mellitus with moderate nonproliferative diabetic retinopathy with macular edema",
)
N18_30_ROW = _code_row("N18.30", "Chronic kidney disease, stage 3 unspecified")
N18_31_ROW = _code_row("N18.31", "Chronic kidney disease, stage 3a")


class TestQueryTokens:
    """
    "type 2" and "stage 3" are single facts. Split into words, the digit was
    dropped as too short, so a type 2 query matched type 1 entries and stage
    3 could not be told apart from 3a or 3b.
    """

    @pytest.mark.parametrize("normalized,expected", [
        ("type 2 diabetes mellitus", ["type 2", "diabetes", "mellitus"]),
        ("chronic kidney disease stage 3b", ["chronic", "kidney", "disease", "stage 3b"]),
        ("ckd stage iiib", ["ckd", "stage 3b"]),
        ("type ii diabetes and ckd", ["type 2", "diabetes", "ckd"]),
        ("pneumonia of the lung", ["pneumonia", "lung"]),
    ])
    def test_tokens(self, normalized, expected):
        assert query_tokens(normalized) == expected


class TestAllTokensSearch:
    """
    The incident: "Type 2 diabetes mellitus" OR-matched "type" inside
    "phenotype" and "karyotype", nothing cleared the floor, and the flat-0.5
    description fallback handed a CKD note E11.331, a retinopathy code.
    """

    DIABETES_INDEX = [
        {"code": "E10.9", "normalized_term": "diabetes diabetic mellitus sugar type 1"},
        {"code": "E11.9", "normalized_term": "diabetes diabetic mellitus sugar type 2"},
        {"code": "E11.36", "normalized_term": "diabetes diabetic mellitus sugar type 2 with cataract"},
    ]

    @pytest.mark.asyncio
    async def test_type_2_query_never_returns_type_1(self, stub_index):
        stub_index["index_rows"] = self.DIABETES_INDEX
        stub_index["icd_rows"] = [E10_9_ROW, E11_9_ROW, E11_36_ROW]
        codes = [r["code"] for r in await search_icd_by_text("Type 2 diabetes mellitus")]
        assert "E10.9" not in codes
        assert set(codes) == {"E11.9", "E11.36"}

    @pytest.mark.asyncio
    async def test_the_plain_index_entry_ranks_first(self, stub_index):
        """Both rows cover the query; the one that says nothing more wins the tie."""
        stub_index["index_rows"] = list(reversed(self.DIABETES_INDEX))
        stub_index["icd_rows"] = [E11_36_ROW, E11_9_ROW]
        results = await search_icd_by_text("Type 2 diabetes mellitus")
        assert results[0]["code"] == "E11.9"

    @pytest.mark.asyncio
    async def test_stage_3_outranks_stage_3a(self, stub_index):
        stub_index["index_rows"] = [
            {"code": "N18.31", "normalized_term": "disease diseased kidney functional pelvis chronic stage 3a"},
            {"code": "N18.30", "normalized_term": "disease diseased kidney functional pelvis chronic stage 3 moderate"},
        ]
        stub_index["icd_rows"] = [N18_30_ROW, N18_31_ROW]
        results = await search_icd_by_text("chronic kidney disease stage 3")
        scores = {r["code"]: r["score"] for r in results}
        assert results[0]["code"] == "N18.30"
        assert scores["N18.30"] > scores["N18.31"]


class TestDescriptionFallback:
    @pytest.mark.asyncio
    async def test_long_unrelated_description_is_dropped(self, stub_index):
        """
        E11.331 contains the whole query but is mostly findings the note never
        mentions. Scored on both sides it falls below the floor.
        """
        stub_index["fallback_rows"] = [E11_331_ROW, E11_9_ROW]
        results = await search_icd_by_text("Type 2 diabetes mellitus")
        codes = [r["code"] for r in results]
        assert "E11.331" not in codes
        assert codes == ["E11.9"]

    @pytest.mark.asyncio
    async def test_no_flat_score(self, stub_index):
        stub_index["fallback_rows"] = [E11_9_ROW]
        results = await search_icd_by_text("Type 2 diabetes mellitus without complications")
        assert results[0]["score"] == 1.0, "an exact description match scores as one"


class TestQueriesAreOrdered:
    """An unordered LIMIT returns whatever Postgres scans first: nondeterministic."""

    @pytest.fixture
    def captured(self, monkeypatch):
        calls = []

        async def fake_select(table, query="*", filters=None, limit=None):
            calls.append((table, filters))
            return []

        monkeypatch.setattr(icd_service, "select", fake_select)
        return calls

    @pytest.mark.asyncio
    async def test_all_tokens_query(self, captured):
        await icd_service._search_index_terms_all(["type 2", "diabetes"])
        table, filters = captured[0]
        assert table == "icd_index_terms"
        assert filters["and"] == "(normalized_term.ilike.*type 2*,normalized_term.ilike.*diabetes*)"
        assert filters["order"] == "normalized_term.asc"

    @pytest.mark.asyncio
    async def test_any_token_query(self, captured):
        await icd_service._search_index_terms("pneumonia", ["pneumonia"])
        assert captured[0][1]["order"] == "normalized_term.asc"

    @pytest.mark.asyncio
    async def test_description_query(self, captured):
        await icd_service._search_descriptions(["type 2", "diabetes"])
        table, filters = captured[0]
        assert table == "icd_codes"
        assert filters["and"] == "(description.ilike.*type 2*,description.ilike.*diabetes*)"
        assert filters["order"] == "code.asc"


class TestCommas:
    """
    A comma inside a PostgREST `and=(...)`/`or=(...)` value splits the
    condition. The old fallback put the raw query, commas included, into
    `ilike`; descriptions are full of commas ("Chronic kidney disease, stage 3").
    """

    @pytest.mark.asyncio
    async def test_query_commas_never_reach_the_filter(self, monkeypatch):
        seen = []

        async def fake_select(table, query="*", filters=None, limit=None):
            seen.append(filters)
            return []

        monkeypatch.setattr(icd_service, "select", fake_select)
        await search_icd_by_text("Chronic kidney disease, stage 3")
        conditions = [f.get("and") or f.get("or") for f in seen]
        assert len(conditions) == 3, "all-tokens, any-token and description passes all ran"
        for cond in conditions:
            parts = cond.strip("()").split(",")
            assert all(".ilike.*" in p for p in parts), cond

    @pytest.mark.asyncio
    async def test_description_with_commas_matches(self, stub_index):
        stub_index["fallback_rows"] = [N18_30_ROW, N18_31_ROW]
        results = await search_icd_by_text("Chronic kidney disease, stage 3")
        scores = {r["code"]: r["score"] for r in results}
        assert results[0]["code"] == "N18.30"
        assert scores["N18.30"] == 0.9, "the whole query, as words"
        assert scores.get("N18.31", 0) < 0.5, "'stage 3' is not a phrase match for 'stage 3a'"
