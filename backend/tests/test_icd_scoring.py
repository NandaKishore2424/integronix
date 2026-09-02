"""
Unit tests for the deterministic ICD scoring in agents/icd_decision.py.

This is where the billing code is actually chosen. The LLM only turns prose
into structured diagnoses; everything that decides which code gets billed is
the pure scoring function exercised here, which is why it must be defensible
line by line to a payer or an auditor.

No network: these call the scoring helpers directly.
"""

import pytest

from agents.icd_decision import (
    _clinical_consistency_score,
    _combination_code_priority,
    _distinguishing_support,
    _final_score,
    _negation_penalty,
    _penalize_unspecified_codes,
    _specificity_score,
)

# The note from the golden set, trimmed to what the scorers read.
PNEUMONIA_NOTE = (
    "Fever and productive cough for 3 days. Dullness to percussion at right base. "
    "Chest X-Ray: right lower lobe consolidation consistent with pneumonia. "
    "Diagnosis: community-acquired pneumonia, right lower lobe."
)

PNEUMONIA_ENTITIES = {
    "diagnoses": [{
        "text": "Community-acquired pneumonia, right lower lobe",
        "evidence_text": "right lower lobe consolidation consistent with pneumonia",
    }]
}

J18_9 = {"code": "J18.9", "description": "Pneumonia, unspecified organism", "confidence": 0.85}
J84_117 = {"code": "J84.117", "description": "Desquamative interstitial pneumonia", "confidence": 0.85}
A50_04 = {"code": "A50.04", "description": "Early congenital syphilitic pneumonia", "confidence": 0.85}


class TestUpcodingRegression:
    """
    The bug this locks down: _specificity_score was len(code) * 0.15, so a
    longer code scored higher purely for being longer. With vector search
    live, the golden pneumonia note resolved to J84.117 "Desquamative
    interstitial pneumonia" over plain J18.9 — a rare variant the chart says
    nothing about. Awarding specificity that documentation does not support
    is upcoding, which is the exact failure this system exists to prevent.

    ICD-10-CM guideline: code to the highest level of specificity SUPPORTED
    BY the documentation.
    """

    def test_unsupported_specific_code_loses_to_supported_general_code(self):
        general = _final_score(J18_9, PNEUMONIA_ENTITIES, PNEUMONIA_NOTE)
        specific = _final_score(J84_117, PNEUMONIA_ENTITIES, PNEUMONIA_NOTE)
        assert general > specific, (
            f"J18.9 ({general}) must outrank J84.117 ({specific}): the chart "
            "never says 'desquamative' or 'interstitial'"
        )

    def test_unrelated_specific_code_also_loses(self):
        general = _final_score(J18_9, PNEUMONIA_ENTITIES, PNEUMONIA_NOTE)
        syphilitic = _final_score(A50_04, PNEUMONIA_ENTITIES, PNEUMONIA_NOTE)
        assert general > syphilitic

    def test_specificity_is_earned_when_the_chart_supports_it(self):
        """The rule is not "prefer general" — it is "prefer documented"."""
        note = (
            "Diagnosis: desquamative interstitial pneumonia confirmed on biopsy."
        )
        entities = {"diagnoses": [{
            "text": "desquamative interstitial pneumonia",
            "evidence_text": "desquamative interstitial pneumonia confirmed on biopsy",
        }]}
        general = _final_score(J18_9, entities, note)
        specific = _final_score(J84_117, entities, note)
        assert specific > general, (
            "when the chart documents the specific variant, the specific code "
            "must win — otherwise the system under-codes"
        )


class TestDistinguishingSupport:
    def test_full_support_when_every_term_is_documented(self):
        support = _distinguishing_support(
            {"description": "Pneumonia"}, PNEUMONIA_ENTITIES, PNEUMONIA_NOTE
        )
        assert support == 1.0

    def test_zero_support_for_undocumented_terms(self):
        support = _distinguishing_support(
            {"description": "Desquamative interstitial"}, PNEUMONIA_ENTITIES, PNEUMONIA_NOTE
        )
        assert support == 0.0

    def test_meta_words_are_not_treated_as_clinical_terms(self):
        """
        "unspecified" and "organism" describe the CODE, not the patient. A note
        will never contain them, so counting them as unsupported would punish
        exactly the codes that are correct when documentation is non-specific.
        """
        support = _distinguishing_support(J18_9, PNEUMONIA_ENTITIES, PNEUMONIA_NOTE)
        assert support == 1.0, "only 'pneumonia' should count, and it is documented"

    def test_description_with_only_meta_words_is_not_penalised(self):
        support = _distinguishing_support(
            {"description": "Other specified disorder, unspecified"}, PNEUMONIA_ENTITIES, ""
        )
        assert support == 1.0


class TestNegationPenalty:
    """
    A candidate implying a complication the chart explicitly rules out must be
    penalised. Without this, a keyword match happily upcodes to a complication
    code — the classic finding in a compliance audit.
    """

    COMPLICATION = {
        "code": "E11.22",
        "description": "Type 2 diabetes mellitus with diabetic chronic kidney disease",
    }

    def test_penalises_complication_the_chart_denies(self):
        entities = {"diagnoses": [{"text": "type 2 diabetes", "evidence_text": ""}]}
        penalty = _negation_penalty(
            self.COMPLICATION, entities, "type 2 diabetes with no evidence of renal disease"
        )
        assert penalty < 0

    def test_no_penalty_when_complication_is_documented(self):
        entities = {"diagnoses": [{
            "text": "type 2 diabetes with chronic kidney disease",
            "evidence_text": "stage 3 chronic kidney disease secondary to diabetes",
        }]}
        penalty = _negation_penalty(
            self.COMPLICATION, entities, "diabetes with stage 3 chronic kidney disease"
        )
        assert penalty == 0.0

    def test_plain_codes_are_never_penalised(self):
        assert _negation_penalty(J18_9, PNEUMONIA_ENTITIES, "no evidence of renal disease") == 0.0


class TestConsistencyScore:
    def test_rewards_terms_present_in_the_evidence(self):
        score = _clinical_consistency_score({"description": "Pneumonia"}, PNEUMONIA_ENTITIES)
        assert score == 1.0

    def test_penalises_terms_absent_from_the_evidence(self):
        score = _clinical_consistency_score(
            {"description": "Desquamative interstitial fibrosis"}, PNEUMONIA_ENTITIES
        )
        assert score == 0.0

    def test_meta_only_description_returns_neutral(self):
        score = _clinical_consistency_score({"description": "other unspecified"}, PNEUMONIA_ENTITIES)
        assert score == 0.5


class TestScoreBounds:
    @pytest.mark.parametrize("candidate", [J18_9, J84_117, A50_04])
    def test_scores_stay_within_zero_and_one(self, candidate):
        score = _final_score(candidate, PNEUMONIA_ENTITIES, PNEUMONIA_NOTE)
        assert 0.0 <= score <= 1.0

    def test_empty_inputs_do_not_raise(self):
        assert 0.0 <= _final_score({"code": "", "description": ""}, {}, "") <= 1.0

    def test_missing_confidence_uses_a_default(self):
        score = _final_score({"code": "J18.9", "description": "Pneumonia"},
                             PNEUMONIA_ENTITIES, PNEUMONIA_NOTE)
        assert score > 0


class TestCombinationPriority:
    def test_combination_codes_are_preferred(self):
        assert _combination_code_priority(
            {"description": "Diabetes with diabetic nephropathy"}) > 0

    def test_plain_codes_get_no_bonus(self):
        assert _combination_code_priority({"description": "Pneumonia"}) == 0.0


class TestUnspecifiedPenalty:
    def test_unspecified_code_penalised_when_a_gold_keyword_is_present(self):
        candidates = [{"code": "I21.9", "description": "Acute MI, unspecified", "final_score": 0.9}]
        out = _penalize_unspecified_codes(candidates, "patient presents with NSTEMI")
        assert out[0]["final_score"] < 0.9

    def test_no_penalty_without_a_specific_descriptor(self):
        candidates = [{"code": "J18.9", "description": "Pneumonia, unspecified", "final_score": 0.9}]
        out = _penalize_unspecified_codes(candidates, "community-acquired pneumonia")
        assert out[0]["final_score"] == 0.9
