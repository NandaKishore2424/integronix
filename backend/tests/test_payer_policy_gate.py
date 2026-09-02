"""
Unit tests for services/payer_policy_gate.py — pure logic, no network.

This module decides whether a claim is auto-approved for payment without a
human ever looking at it. It is the highest-consequence pure function in the
codebase and had no test coverage; a regression here pays money incorrectly.

The tests are written around one principle: the gate must FAIL CLOSED. Every
test that expects approval states every condition it depends on, so a future
change that loosens a default breaks a test rather than quietly widening what
gets auto-paid.
"""

import pytest

from services.payer_policy_gate import (
    derive_proposed_icd_version,
    run_payer_policy_gate,
)


def _clean_claim(**overrides) -> dict:
    """A claim that satisfies every gate condition."""
    claim = {
        "confidence_score": 0.95,
        "risk_score": 0.10,
        "mapping_path": "direct",
        "patient_dob": "1988-04-15",
        "patient_sex": "F",
        "cpt_codes": [{"code": "71045", "base_price": 27.53}],
        "extraction_metadata": {"icd_version": "ICD-10"},
        "financial_summary": {"total_estimated_revenue": 100.0},
    }
    claim.update(overrides)
    return claim


def _enabled_policy(**overrides) -> dict:
    """A payer policy with auto-approval switched on."""
    policy = {
        "auto_approve_enabled": True,
        "auto_approve_confidence_min": 0.80,
        "auto_approve_max_risk": 0.35,
        "auto_approve_requires_patient_dob": True,
        "auto_approve_requires_patient_sex": True,
        "accepted_icd_versions": ["ICD-10", "ICD-11"],
    }
    policy.update(overrides)
    return policy


def _codes(report: dict) -> set[str]:
    return {r["code"] for r in report["reasons"]}


# ── The fail-closed contract ─────────────────────────────────────────────────

class TestFailsClosed:
    def test_auto_approve_defaults_off(self):
        """
        A payer with NO policy configured must never auto-approve, even on a
        flawless claim. Absence of configuration is not consent to pay.
        """
        report = run_payer_policy_gate(
            claim_data=_clean_claim(), payer_policy={}, org_settings=None
        )
        assert report["should_auto_approve"] is False

    def test_empty_claim_does_not_pass(self):
        report = run_payer_policy_gate(
            claim_data={}, payer_policy=_enabled_policy(), org_settings=None
        )
        assert report["gate_status"] == "NEEDS_REVIEW"
        assert report["should_auto_approve"] is False

    def test_gate_pass_still_requires_the_payer_switch(self):
        """A claim can clear every check and still not be paid automatically."""
        report = run_payer_policy_gate(
            claim_data=_clean_claim(),
            payer_policy=_enabled_policy(auto_approve_enabled=False),
            org_settings=None,
        )
        assert report["gate_status"] == "PASS"
        assert report["should_auto_approve"] is False


class TestApprovesOnlyWhenEverythingHolds:
    def test_clean_claim_with_enabled_policy_auto_approves(self):
        report = run_payer_policy_gate(
            claim_data=_clean_claim(),
            payer_policy=_enabled_policy(),
            org_settings={"coding_mode": "balanced"},
        )
        assert report["reasons"] == []
        assert report["gate_status"] == "PASS"
        assert report["should_auto_approve"] is True


# ── Individual gates ─────────────────────────────────────────────────────────

class TestDemographicsGate:
    def test_missing_dob_blocks(self):
        report = run_payer_policy_gate(
            claim_data=_clean_claim(patient_dob=None),
            payer_policy=_enabled_policy(),
            org_settings=None,
        )
        assert "MISSING_DOB" in _codes(report)
        assert report["should_auto_approve"] is False

    def test_missing_sex_blocks(self):
        report = run_payer_policy_gate(
            claim_data=_clean_claim(patient_sex=None),
            payer_policy=_enabled_policy(),
            org_settings=None,
        )
        assert "MISSING_SEX" in _codes(report)

    def test_future_dob_blocks(self):
        report = run_payer_policy_gate(
            claim_data=_clean_claim(patient_dob="2999-01-01"),
            payer_policy=_enabled_policy(),
            org_settings=None,
        )
        assert "DOB_IN_FUTURE" in _codes(report)

    def test_payer_may_waive_demographics(self):
        report = run_payer_policy_gate(
            claim_data=_clean_claim(patient_dob=None, patient_sex=None),
            payer_policy=_enabled_policy(
                auto_approve_requires_patient_dob=False,
                auto_approve_requires_patient_sex=False,
            ),
            org_settings=None,
        )
        assert "MISSING_DOB" not in _codes(report)
        assert "MISSING_SEX" not in _codes(report)


class TestConfidenceAndRisk:
    def test_low_confidence_blocks(self):
        report = run_payer_policy_gate(
            claim_data=_clean_claim(confidence_score=0.50),
            payer_policy=_enabled_policy(),
            org_settings=None,
        )
        assert "LOW_CONFIDENCE" in _codes(report)

    def test_high_risk_blocks(self):
        report = run_payer_policy_gate(
            claim_data=_clean_claim(risk_score=0.90),
            payer_policy=_enabled_policy(),
            org_settings=None,
        )
        assert "HIGH_RISK" in _codes(report)

    def test_confidence_exactly_at_threshold_passes(self):
        """`<` not `<=` — a claim exactly at the configured floor is allowed."""
        report = run_payer_policy_gate(
            claim_data=_clean_claim(confidence_score=0.80),
            payer_policy=_enabled_policy(auto_approve_confidence_min=0.80),
            org_settings={"coding_mode": "balanced"},
        )
        assert "LOW_CONFIDENCE" not in _codes(report)


class TestMappingQuality:
    @pytest.mark.parametrize("path", ["no_mapping", "embedding_failed", "unknown", "no_snomed"])
    def test_unresolved_mapping_paths_block(self, path):
        """
        These paths mean the pipeline never actually resolved a code. This is
        the gate that would have caught the "abrasion of lower back" incident
        reaching a payer.
        """
        report = run_payer_policy_gate(
            claim_data=_clean_claim(mapping_path=path),
            payer_policy=_enabled_policy(),
            org_settings=None,
        )
        assert "MAPPING_UNRESOLVED" in _codes(report)
        assert report["should_auto_approve"] is False

    @pytest.mark.parametrize("path", ["direct", "embedding", "who_api_icd10"])
    def test_trusted_mapping_paths_do_not_block(self, path):
        report = run_payer_policy_gate(
            claim_data=_clean_claim(mapping_path=path),
            payer_policy=_enabled_policy(),
            org_settings=None,
        )
        assert "MAPPING_UNRESOLVED" not in _codes(report)
        assert "MAPPING_QUALITY_WEAK" not in _codes(report)

    def test_unrecognised_path_is_review_not_reject(self):
        report = run_payer_policy_gate(
            claim_data=_clean_claim(mapping_path="some_new_path"),
            payer_policy=_enabled_policy(),
            org_settings=None,
        )
        assert "MAPPING_QUALITY_WEAK" in _codes(report)
        weak = next(r for r in report["reasons"] if r["code"] == "MAPPING_QUALITY_WEAK")
        assert weak["severity"] == "MEDIUM"


class TestIcdVersionCompatibility:
    def test_rejected_when_payer_does_not_accept_the_version(self):
        report = run_payer_policy_gate(
            claim_data=_clean_claim(extraction_metadata={"icd_version": "ICD-11"}),
            payer_policy=_enabled_policy(accepted_icd_versions=["ICD-10"]),
            org_settings=None,
        )
        assert "ICD_VERSION_REJECTED" in _codes(report)

    def test_undeterminable_version_requires_review(self):
        report = run_payer_policy_gate(
            claim_data=_clean_claim(extraction_metadata={}, mapping_path="direct"),
            payer_policy=_enabled_policy(),
            org_settings=None,
        )
        assert "ICD_VERSION_UNKNOWN" in _codes(report)

    def test_accepted_versions_as_json_string_does_not_crash(self):
        """Supabase can hand back a JSON column as text; the gate must cope."""
        report = run_payer_policy_gate(
            claim_data=_clean_claim(),
            payer_policy=_enabled_policy(accepted_icd_versions='["ICD-10"]'),
            org_settings=None,
        )
        assert "ICD_VERSION_REJECTED" not in _codes(report)


class TestProcedureAndDiscrepancyGates:
    def test_no_cpt_codes_requires_review(self):
        report = run_payer_policy_gate(
            claim_data=_clean_claim(cpt_codes=[]),
            payer_policy=_enabled_policy(),
            org_settings=None,
        )
        assert "NO_CPT_CODES" in _codes(report)

    @pytest.mark.parametrize("discrepancy", ["UNSUPPORTED_CODE", "OVERCODING"])
    def test_coding_discrepancies_block(self, discrepancy):
        report = run_payer_policy_gate(
            claim_data=_clean_claim(discrepancy_type=discrepancy),
            payer_policy=_enabled_policy(),
            org_settings=None,
        )
        assert "DISCREPANCY_FAIL" in _codes(report)


class TestCustomRules:
    """
    Regression tests for two payer-configured safety rules that silently did
    nothing. Both were found by these tests, not in review.

    max_amount read claim_data["total_billed_amount"], a key that is never
    present — the API takes the amount as a sibling of claim_data. It always
    compared 0.0 > threshold, so a payer's spending cap never once blocked a
    claim. exclude_cpt_prefix looked for item["cpt_code"] while the pipeline
    emits item["code"], so it matched nothing.
    """

    CAP_RULE = {"rule_type": "max_amount", "label": "Cap at 1 lakh", "threshold": 100_000.0}

    def test_max_amount_blocks_when_amount_passed_explicitly(self):
        """The route's own path: total_billed_amount comes in as an argument."""
        report = run_payer_policy_gate(
            claim_data=_clean_claim(),
            payer_policy=_enabled_policy(auto_approve_custom_rules=[self.CAP_RULE]),
            org_settings=None,
            total_billed_amount=500_000.0,
        )
        assert "CUSTOM_MAX_AMOUNT" in _codes(report)
        assert report["should_auto_approve"] is False

    def test_max_amount_falls_back_to_pipeline_total(self):
        """No explicit amount — the pipeline's own revenue total is used."""
        report = run_payer_policy_gate(
            claim_data=_clean_claim(
                financial_summary={"total_estimated_revenue": 500_000.0}
            ),
            payer_policy=_enabled_policy(auto_approve_custom_rules=[self.CAP_RULE]),
            org_settings=None,
        )
        assert "CUSTOM_MAX_AMOUNT" in _codes(report)
        assert report["should_auto_approve"] is False

    def test_max_amount_allows_claims_under_the_cap(self):
        report = run_payer_policy_gate(
            claim_data=_clean_claim(),
            payer_policy=_enabled_policy(auto_approve_custom_rules=[self.CAP_RULE]),
            org_settings={"coding_mode": "balanced"},
            total_billed_amount=5_000.0,
        )
        assert "CUSTOM_MAX_AMOUNT" not in _codes(report)
        assert report["should_auto_approve"] is True

    def test_excluded_cpt_prefix_matches_the_pipelines_own_key(self):
        """The pipeline emits "code"; the rule must not only honour "cpt_code"."""
        report = run_payer_policy_gate(
            claim_data=_clean_claim(cpt_codes=[{"code": "27447", "base_price": 900.0}]),
            payer_policy=_enabled_policy(auto_approve_custom_rules=[
                {"rule_type": "exclude_cpt_prefix", "label": "No joint replacement",
                 "code_prefix": "274"}
            ]),
            org_settings=None,
        )
        assert "CUSTOM_EXCLUDED_CPT" in _codes(report)
        assert report["should_auto_approve"] is False

    def test_excluded_cpt_prefix_still_honours_legacy_key(self):
        report = run_payer_policy_gate(
            claim_data=_clean_claim(cpt_codes=[{"cpt_code": "27447", "base_price": 900.0}]),
            payer_policy=_enabled_policy(auto_approve_custom_rules=[
                {"rule_type": "exclude_cpt_prefix", "label": "No joint replacement",
                 "code_prefix": "274"}
            ]),
            org_settings=None,
        )
        assert "CUSTOM_EXCLUDED_CPT" in _codes(report)

    def test_non_matching_prefix_does_not_block(self):
        report = run_payer_policy_gate(
            claim_data=_clean_claim(cpt_codes=[{"code": "71045", "base_price": 27.53}]),
            payer_policy=_enabled_policy(auto_approve_custom_rules=[
                {"rule_type": "exclude_cpt_prefix", "label": "No joint replacement",
                 "code_prefix": "274"}
            ]),
            org_settings={"coding_mode": "balanced"},
        )
        assert "CUSTOM_EXCLUDED_CPT" not in _codes(report)
        assert report["should_auto_approve"] is True

    def test_age_rules_evaluate_against_dob(self):
        report = run_payer_policy_gate(
            claim_data=_clean_claim(patient_dob="2020-01-01"),
            payer_policy=_enabled_policy(auto_approve_custom_rules=[
                {"rule_type": "require_min_age", "label": "Adults only", "min_age": 18}
            ]),
            org_settings=None,
        )
        assert "CUSTOM_AGE_TOO_LOW" in _codes(report)

    def test_malformed_custom_rules_do_not_crash_the_gate(self):
        """Rules are payer-authored data; bad input must not 500 a submission."""
        report = run_payer_policy_gate(
            claim_data=_clean_claim(),
            payer_policy=_enabled_policy(auto_approve_custom_rules=[
                {"rule_type": "nonsense_rule", "label": "?"},
                {},
            ]),
            org_settings=None,
        )
        assert report["gate_status"] in {"PASS", "NEEDS_REVIEW"}


class TestCodingModeThresholds:
    """
    NOTE — documents CURRENT behaviour, which is likely not the intent.

    Both "aggressive" and "conservative" TIGHTEN the confidence floor
    (by 0.05 and 0.02); only "balanced" is neutral. So a conservative hospital
    — one that under-codes, and therefore poses less over-billing risk — is
    held to a stricter standard than a balanced one. The asymmetry is
    deliberate in shape but the conservative direction looks inverted.

    These tests pin the behaviour so it cannot drift silently. If the
    direction is corrected, this class should be updated in the same commit.
    """

    def test_aggressive_mode_tightens_confidence_floor(self):
        claim = _clean_claim(confidence_score=0.82)
        policy = _enabled_policy(auto_approve_confidence_min=0.80)

        balanced = run_payer_policy_gate(
            claim_data=claim, payer_policy=policy,
            org_settings={"coding_mode": "balanced"})
        aggressive = run_payer_policy_gate(
            claim_data=claim, payer_policy=policy,
            org_settings={"coding_mode": "aggressive"})

        assert "LOW_CONFIDENCE" not in _codes(balanced)
        assert "LOW_CONFIDENCE" in _codes(aggressive), "0.82 < 0.80 + 0.05"

    def test_conservative_mode_also_tightens(self):
        claim = _clean_claim(confidence_score=0.81)
        policy = _enabled_policy(auto_approve_confidence_min=0.80)

        conservative = run_payer_policy_gate(
            claim_data=claim, payer_policy=policy,
            org_settings={"coding_mode": "conservative"})

        assert "LOW_CONFIDENCE" in _codes(conservative), "0.81 < 0.80 + 0.02"


class TestDeriveProposedIcdVersion:
    def test_reads_explicit_metadata_first(self):
        assert derive_proposed_icd_version(
            {"extraction_metadata": {"icd_version": "ICD-11"}, "mapping_path": "who_api_icd10"}
        ) == "ICD-11"

    def test_falls_back_to_mapping_path(self):
        assert derive_proposed_icd_version({"mapping_path": "who_api_icd11"}) == "ICD-11"
        assert derive_proposed_icd_version({"mapping_path": "who_api_icd10"}) == "ICD-10"

    def test_returns_none_when_undeterminable(self):
        assert derive_proposed_icd_version({"mapping_path": "embedding"}) is None
        assert derive_proposed_icd_version({}) is None
