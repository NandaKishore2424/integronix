"""
agents/risk_scoring.py — Node 8: Risk Scoring + DB Write

Final node in the pipeline. Computes risk score and writes
complete results to Supabase (clinical_cases + coding_results + audit_log).

Risk formula:
  Base: confidence inversion (low confidence → higher risk)
  Boost: discrepancy type, IS_MCC, financial_delta magnitude

Labels:
  LOW    → score < 0.35
  MEDIUM → score 0.35–0.70
  HIGH   → score > 0.70
"""
import uuid
from datetime import datetime, timezone
from agents.graph import CodingState
from agents.node_runner import safe_node
from database import insert, select_one
from config import settings
from logger import get_logger, Timer

log = get_logger(__name__)

# Risk weight constants
DISCREPANCY_RISK = {
    "EXACT_MATCH":              0.0,
    "NO_COMPARISON":            0.1,
    "SPECIFICITY_IMPROVEMENT":  0.2,
    "OVERCODING":               0.5,
    "UNSUPPORTED_CODE":         0.6,
}


def _compute_risk(state: CodingState) -> tuple[float, str]:
    """
    Deterministic risk computation.
    Returns (risk_score: float, risk_label: str).
    """
    confidence   = float(state.get("confidence_score", 0.5))
    discrepancy  = state.get("discrepancy_type", "NO_COMPARISON")
    delta        = abs(state.get("financial_delta") or 0.0)
    drg_flag     = state.get("drg_flag")
    is_mcc       = False

    # Check if final code is MCC
    candidates = state.get("candidate_icd_codes", [])
    final_code = state.get("final_icd_code", "")
    for c in candidates:
        if c.get("code") == final_code and c.get("is_mcc"):
            is_mcc = True
            break

    # Base risk = inverted confidence
    base_risk = round(1.0 - confidence, 4)

    # Discrepancy risk
    discrepancy_boost = DISCREPANCY_RISK.get(discrepancy, 0.2)

    # Financial delta risk (large delta = higher scrutiny)
    delta_boost = min(delta / 5000.0, 0.2)

    # DRG-aware MCC/CC boost
    if drg_flag == "MCC_MISSED":
        mcc_boost = 0.20   # Significant DRG weight impact
    elif drg_flag in ("CC_MISSED", "MCC_OVERCODED"):
        mcc_boost = 0.15
    elif is_mcc:
        mcc_boost = 0.10   # Normal MCC scrutiny
    else:
        mcc_boost = 0.0

    raw_score = base_risk * 0.4 + discrepancy_boost * 0.4 + delta_boost * 0.1 + mcc_boost * 0.1
    score = round(min(raw_score, 1.0), 4)

    label = "LOW" if score < 0.35 else ("MEDIUM" if score <= 0.70 else "HIGH")
    return score, label


@safe_node("risk_scoring")
async def risk_scoring_node(state: CodingState) -> CodingState:
    """
    LangGraph Node 8 — Risk Scoring + DB Write.
    Input:  full state after Nodes 1-7
    Output: state["risk_score"], state["risk_label"] + writes to Supabase
    """
    session_id = str(state.get("session_id", str(uuid.uuid4())))

    # ── Compute risk ────────────────────────────────────────────────────────
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
            "confidence_score":     risk_score,
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
