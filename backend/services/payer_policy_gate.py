"""
services/payer_policy_gate.py

Implements the payer "trust gate" for auto-approve.

Design goal (India use-case / hackathon v1):
- Hospitals propose codes + demographics (from extracted PDF).
- Payers decide acceptance using their own policy config.
- Auto-approve is enabled only when the payer explicitly turns it on AND the
  hospital proposal passes deterministic checks.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from logger import get_logger

log = get_logger(__name__)


APPROVABLE_MAPPING_PATHS = {
    "direct",
    "embedding",
    "who_api_icd11",
    "who_api_icd10",
    "provider_fallback",
    "provider_augmented",
}

# These should never be auto-approved in V1.
REJECT_MAPPING_PATHS = {"no_mapping", "embedding_failed", "unknown", "no_snomed"}


def _norm_sex(sex: Optional[str]) -> Optional[str]:
    if not sex:
        return None
    s = sex.strip().upper()
    if s in {"M", "MALE"}:
        return "M"
    if s in {"F", "FEMALE"}:
        return "F"
    if s in {"O", "OTHER", "X", "NON-BINARY"}:
        return "O"
    return None


def _try_parse_date(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str:
        return None
    s = str(date_str).strip()
    if not s:
        return None
    # Accept "YYYY-MM-DD" only (hospital may extract with this format)
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except Exception:
        return None


def derive_proposed_icd_version(claim_data: dict) -> Optional[str]:
    """
    Determine which ICD system the hospital proposal is using.
    Prefer extraction_metadata.icd_version; fall back to mapping_path.
    """
    meta = claim_data.get("extraction_metadata") or {}
    icd_version = (meta.get("icd_version") or "").strip().upper()
    if icd_version == "ICD-11" or "ICD-11" in icd_version:
        return "ICD-11"
    if icd_version == "ICD-10" or "ICD-10" in icd_version:
        return "ICD-10"

    mp = (claim_data.get("mapping_path") or "").lower()
    if "who_api_icd11" in mp:
        return "ICD-11"
    if "who_api_icd10" in mp:
        return "ICD-10"
    return None


def _add_reason(reasons: list[dict], code: str, message: str, severity: str) -> None:
    reasons.append({"code": code, "message": message, "severity": severity})


def run_payer_policy_gate(
    *,
    claim_data: dict,
    payer_policy: dict,
    org_settings: Optional[dict] = None,
) -> dict:
    """
    Returns a report:
      {
        gate_status: "PASS" | "NEEDS_REVIEW",
        should_auto_approve: bool,
        reasons: [{code,message,severity}],
        signals: {confidence_score, risk_score, icd_version, mapping_path, ...}
      }
    """
    reasons: list[dict] = []

    confidence_score = float(claim_data.get("confidence_score") or 0.0)
    risk_score = float(claim_data.get("risk_score") or 0.0)
    mapping_path = (claim_data.get("mapping_path") or "unknown").strip()

    patient_dob_raw = claim_data.get("patient_dob")
    patient_sex_raw = claim_data.get("patient_sex")

    patient_dob_dt = _try_parse_date(patient_dob_raw)
    patient_sex = _norm_sex(patient_sex_raw)

    proposal_icd_version = derive_proposed_icd_version(claim_data)

    # Coding mode can tighten thresholds for "aggressive" hospitals.
    coding_mode = (org_settings or {}).get("coding_mode") if org_settings else None

    requires_dob = bool(payer_policy.get("auto_approve_requires_patient_dob", True))
    requires_sex = bool(payer_policy.get("auto_approve_requires_patient_sex", True))

    # Config thresholds (payer-configured).
    conf_min = float(payer_policy.get("auto_approve_confidence_min") or 0.80)
    max_risk = float(payer_policy.get("auto_approve_max_risk") or 0.35)
    auto_enabled = bool(payer_policy.get("auto_approve_enabled", False))

    accepted_icd_versions = payer_policy.get("accepted_icd_versions") or ["ICD-10", "ICD-11"]
    if isinstance(accepted_icd_versions, str):
        # Defensive: if Supabase returns JSON as a string, handle it best-effort.
        try:
            import json

            accepted_icd_versions = json.loads(accepted_icd_versions)
        except Exception:
            accepted_icd_versions = ["ICD-10", "ICD-11"]

    # --- Required demographics gate ---
    if requires_dob and not patient_dob_dt:
        _add_reason(
            reasons,
            code="MISSING_DOB",
            message="Auto-approve requires a documented patient date of birth (YYYY-MM-DD).",
            severity="HIGH",
        )

    if requires_sex and not patient_sex:
        _add_reason(
            reasons,
            code="MISSING_SEX",
            message="Auto-approve requires a documented patient sex (M/F/other).",
            severity="HIGH",
        )

    # Validate plausibility (very light check; no PHI inference)
    if patient_dob_dt and patient_dob_dt.year > datetime.utcnow().year:
        _add_reason(
            reasons,
            code="DOB_IN_FUTURE",
            message="Patient DOB appears to be in the future; payer will require manual review.",
            severity="HIGH",
        )

    # --- ICD version compatibility ---
    if proposal_icd_version and accepted_icd_versions:
        if proposal_icd_version not in accepted_icd_versions:
            _add_reason(
                reasons,
                code="ICD_VERSION_REJECTED",
                message=f"Proposed ICD system ({proposal_icd_version}) is not accepted for this payer policy.",
                severity="HIGH",
            )
    elif accepted_icd_versions:
        _add_reason(
            reasons,
            code="ICD_VERSION_UNKNOWN",
            message="Could not determine ICD version for the proposal; require manual review.",
            severity="HIGH",
        )

    # --- Mapping quality gate ---
    if mapping_path in REJECT_MAPPING_PATHS:
        _add_reason(
            reasons,
            code="MAPPING_UNRESOLVED",
            message=f"Mapping path '{mapping_path}' is not eligible for auto-approve.",
            severity="HIGH",
        )
    elif mapping_path not in APPROVABLE_MAPPING_PATHS:
        # Keep this as NEEDS_REVIEW rather than outright reject, so payer can still review.
        _add_reason(
            reasons,
            code="MAPPING_QUALITY_WEAK",
            message=f"Mapping path '{mapping_path}' is not a top-tier source; require review.",
            severity="MEDIUM",
        )

    # --- Confidence / risk thresholds ---
    # Indian insurance practice: auto-approval is normally used only for low-risk / high-confidence
    # proposals to reduce coding disputes.
    conf_delta = 0.0
    risk_delta = 0.0
    if coding_mode == "aggressive":
        conf_delta = 0.05
        risk_delta = 0.05
    elif coding_mode == "conservative":
        conf_delta = 0.02
        risk_delta = 0.02

    if confidence_score < (conf_min + conf_delta):
        _add_reason(
            reasons,
            code="LOW_CONFIDENCE",
            message=f"Confidence score {confidence_score:.2f} is below auto-approve threshold.",
            severity="MEDIUM",
        )

    if risk_score > (max_risk - risk_delta):
        _add_reason(
            reasons,
            code="HIGH_RISK",
            message=f"Risk score {risk_score:.2f} exceeds auto-approve maximum.",
            severity="MEDIUM",
        )

    # --- Procedure presence (for EDI 837 plausibility) ---
    cpt_codes = claim_data.get("cpt_codes") or []
    if not isinstance(cpt_codes, list) or len(cpt_codes) == 0:
        _add_reason(
            reasons,
            code="NO_CPT_CODES",
            message="No procedure codes were proposed; payer may require manual review before claim submission.",
            severity="MEDIUM",
        )

    discrepancy_type = claim_data.get("discrepancy_type")
    if discrepancy_type and discrepancy_type in {"UNSUPPORTED_CODE", "OVERCODING"}:
        _add_reason(
            reasons,
            code="DISCREPANCY_FAIL",
            message=f"Discrepancy type '{discrepancy_type}' suggests a coding mismatch; requires review.",
            severity="HIGH",
        )

    gate_status = "PASS" if not reasons else "NEEDS_REVIEW"

    should_auto_approve = auto_enabled and gate_status == "PASS"

    report = {
        "gate_status": gate_status,
        "should_auto_approve": should_auto_approve,
        "reasons": reasons,
        "signals": {
            "confidence_score": confidence_score,
            "risk_score": risk_score,
            "mapping_path": mapping_path,
            "proposed_icd_version": proposal_icd_version,
            "patient_dob_present": bool(patient_dob_dt),
            "patient_sex_present": bool(patient_sex),
            "coding_mode": coding_mode,
        },
    }

    log.info("payer_policy_gate", auto_enabled=auto_enabled, gate_status=gate_status, reasons_count=len(reasons))
    return report

