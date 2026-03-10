"""
This is the final agent in our pipeline. It calculates a risk score for the
entire coding process and then writes all the results to our database.
The risk score helps auditors prioritize which cases to review.
"""
import uuid
from datetime import datetime, timezone
from agents.graph import CodingState
from agents.node_runner import safe_node
from database import insert, select_one
from config import settings
from logger import get_logger, Timer

log = get_logger(__name__)

# These are the weights we use to calculate risk based on the type of discrepancy.
# For example, an "OVERCODING" issue is riskier than a "SPECIFICITY_IMPROVEMENT".
DISCREPANCY_RISK = {
    "EXACT_MATCH":              0.0,
    "NO_COMPARISON":            0.1,
    "SPECIFICITY_IMPROVEMENT":  0.2,
    "CODE_DIVERGENCE":          0.45,  # Different category — potential wrong code entirely
    "OVERCODING":               0.5,
    "UNSUPPORTED_CODE":         0.6,
}


def _compute_risk(state: CodingState) -> tuple[float, str]:
    # This function calculates the final risk score based on several factors.
    confidence   = float(state.get("confidence_score", 0.5))
    discrepancy  = state.get("discrepancy_type", "NO_COMPARISON")
    delta        = abs(state.get("financial_delta") or 0.0)
    drg_flag     = state.get("drg_flag")
    is_mcc       = False

    # First, we check if the final selected code is a Major Complication (MCC).
    # MCCs have a higher impact on reimbursement, so they carry more risk.
    candidates = state.get("candidate_icd_codes", [])
    final_code = state.get("final_icd_code", "")
    for c in candidates:
        if c.get("code") == final_code and c.get("is_mcc"):
            is_mcc = True
            break

    # The base risk is simply the inverse of our confidence score.
    # Low confidence means high risk.
    base_risk = round(1.0 - confidence, 4)

    # Add risk based on the type of discrepancy found during the audit.
    discrepancy_boost = DISCREPANCY_RISK.get(discrepancy, 0.2)

    # A larger financial impact (positive or negative) increases the risk.
    delta_boost = min(delta / 5000.0, 0.2)

    # Missing or overcoding a DRG-related code (MCC/CC) significantly increases risk.
    if drg_flag == "MCC_MISSED":
        mcc_boost = 0.20
    elif drg_flag in ("CC_MISSED", "MCC_OVERCODED"):
        mcc_boost = 0.15
    elif is_mcc:
        mcc_boost = 0.10
    else:
        mcc_boost = 0.0

    # Combine all the factors into a final score.
    raw_score = base_risk * 0.4 + discrepancy_boost * 0.4 + delta_boost * 0.1 + mcc_boost * 0.1
    score = round(min(raw_score, 1.0), 4)

    # Assign a simple label based on the score.
    label = "LOW" if score < 0.35 else ("MEDIUM" if score <= 0.70 else "HIGH")
    return score, label


@safe_node("risk_scoring")
async def risk_scoring_node(state: CodingState) -> CodingState:
    # This is the main function for the final node in our graph.
    session_id = str(state.get("session_id", str(uuid.uuid4())))

    # First, we calculate the risk score and label.
    risk_score, risk_label = _compute_risk(state)
    state["risk_score"] = risk_score
    state["risk_label"] = risk_label

    log.info(
        "risk_computed",
        session_id=session_id,
        risk_score=risk_score,
        risk_label=risk_label,
        final_icd_code=state.get("final_icd_code"),
        confidence_score=state.get("confidence_score"),
    )

    # ── Write clinical_cases row ────────────────────────────────────────────
    try:
        await insert("clinical_cases", {
            "session_id":           session_id,
            "structured_entities":  state.get("structured_entities"),
            "processing_status":    "COMPLETE",
            "completed_at":         datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        log.warning("clinical_cases_write_failed", session_id=session_id, error=str(e))

    # ── Write coding_results row ────────────────────────────────────────────
    discrepancy = state.get("discrepancy") or {}
    try:
        await insert("coding_results", {
            "case_id":              None,   # Set after case_id lookup if needed
            "resolved_snomed_code": state.get("resolved_snomed_code"),
            "mapping_path":         state.get("mapping_path"),
            "ai_icd_code":          state.get("final_icd_code"),
            "confidence_score":     state.get("confidence_score", 0.0),   # FIX: was storing risk_score here
            "candidate_codes":      state.get("candidate_icd_codes", []),
            "human_icd_code":       state.get("human_icd_code"),
            "discrepancy_type":     state.get("discrepancy_type", "NO_COMPARISON"),
            "evidence_text":        (state.get("structured_entities") or {})
                                    .get("diagnoses", [{}])[0]
                                    .get("evidence_text", ""),
            "financial_delta":      state.get("financial_delta", 0.0),
            "risk_score":           risk_score,
            "risk_label":           risk_label,
            "audit_result_json":    discrepancy,
        })
    except Exception as e:
        log.warning("coding_results_write_failed", session_id=session_id, error=str(e))

    # ── Write audit_log entry for this final node ───────────────────────────
    metadata = state.get("extraction_metadata") or {}
    try:
        await insert("audit_log", {
            "session_id":   session_id,
            "node_name":    "risk_scoring",
            "output_snapshot": {
                "final_icd_code":   state.get("final_icd_code"),
                "icd_codes":        state.get("icd_codes", []),
                "confidence_score": state.get("confidence_score"),
                "risk_score":       risk_score,
                "risk_label":       risk_label,
                "discrepancy_type": state.get("discrepancy_type"),
                "financial_delta":  state.get("financial_delta"),
                "drg_flag":         state.get("drg_flag"),
            },
            "model_name":     metadata.get("model"),
            "model_version":  metadata.get("llm_version"),
            "icd_version":    settings.icd_version,
            "snomed_version": settings.snomed_version,
            "status":         "success",
        })
    except Exception as e:
        log.warning("audit_log_write_failed", session_id=session_id, error=str(e))

    return state
