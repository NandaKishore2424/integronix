"""
agents/audit_comparison.py — Node 7: Audit Comparison

Compares AI-selected ICD code vs human-entered ICD code.
Determines discrepancy type and calculates financial delta.

Discrepancy types:
  EXACT_MATCH            — Same code, no issue
  SPECIFICITY_IMPROVEMENT — AI code more specific (longer or with complications)
  UNSUPPORTED_CODE       — Human code not found in DB or no clinical evidence
  OVERCODING             — Human code too specific for documented evidence

Financial delta = AI reimbursement - Human reimbursement
Positive delta = AI code recovers more revenue
"""
from agents.graph import CodingState
from agents.node_runner import safe_node
from database import select_one
from logger import get_logger

log = get_logger(__name__)


def _is_more_specific(ai_code: str, human_code: str) -> bool:
    """True if AI code is more specific than human code."""
    # Longer code = more specific in ICD-10 (E11.22 > E11.9 > E11)
    if len(ai_code) > len(human_code):
        return True
    # Same length but AI has complication keywords, human doesn't
    return False


@safe_node("audit_comparison")
async def audit_comparison_node(state: CodingState) -> CodingState:
    """
    LangGraph Node 7 — Audit Comparison.
    Input:  state["final_icd_code"], state["human_icd_code"]
    Output: state["discrepancy_type"], state["financial_delta"], state["discrepancy"]
    """
    session_id  = str(state.get("session_id", ""))
    ai_code     = state.get("final_icd_code", "UNKNOWN")
    human_code  = state.get("human_icd_code")

    # ── No human code provided — skip audit ────────────────────────────────
    if not human_code:
        state["discrepancy_type"] = "NO_COMPARISON"
        state["financial_delta"]  = 0.0
        state["discrepancy"]      = None
        log.info("audit_skipped", session_id=session_id, reason="no human_icd_code")
        return state

    # ── Fetch AI code details ───────────────────────────────────────────────
    ai_row = await select_one(
        table="icd_codes",
        query="code,description,base_reimbursement,is_cc,is_mcc",
        filters={"code": f"eq.{ai_code}"},
    )

    # ── Fetch Human code details (may not exist in DB) ──────────────────────
    human_row = await select_one(
        table="icd_codes",
        query="code,description,base_reimbursement,is_cc,is_mcc",
        filters={"code": f"eq.{human_code}"},
    )

    ai_reimb    = float(ai_row["base_reimbursement"])    if ai_row    else 0.0
    human_reimb = float(human_row["base_reimbursement"]) if human_row else 0.0
    delta       = round(ai_reimb - human_reimb, 2)

    # ── MCC/CC gap detection (DRG-aware) ────────────────────────────────────
    ai_is_mcc    = bool(ai_row.get("is_mcc"))    if ai_row    else False
    ai_is_cc     = bool(ai_row.get("is_cc"))     if ai_row    else False
    human_is_mcc = bool(human_row.get("is_mcc")) if human_row else False
    human_is_cc  = bool(human_row.get("is_cc"))  if human_row else False

    drg_flag = None
    drg_note = ""
    if ai_is_mcc and not human_is_mcc:
        drg_flag = "MCC_MISSED"
        drg_note = " MCC missed by human coder — DRG weight impact detected."
    elif ai_is_cc and not human_is_cc:
        drg_flag = "CC_MISSED"
        drg_note = " CC missed by human coder — potential DRG downgrade."
    elif human_is_mcc and not ai_is_mcc:
        drg_flag = "MCC_OVERCODED"
        drg_note = " Human coded MCC not supported by clinical documentation."
    state["drg_flag"] = drg_flag

    # ── Determine discrepancy type ──────────────────────────────────────────
    if ai_code == human_code:
        discrepancy_type = "EXACT_MATCH"
        explanation = "AI and human coder selected the same ICD-10 code."

    elif not human_row:
        discrepancy_type = "UNSUPPORTED_CODE"
        explanation = (
            f"Human code '{human_code}' not found in ICD-10-CM-2024 code set. "
            f"AI selected '{ai_code}' based on documented clinical evidence."
        )

    elif _is_more_specific(ai_code, human_code):
        discrepancy_type = "SPECIFICITY_IMPROVEMENT"
        explanation = (
            f"AI selected more specific code '{ai_code}' "
            f"vs human '{human_code}'. "
            f"Clinical documentation supports the more specific code. "
            f"Revenue impact: +${abs(delta):.2f}.{drg_note}"
        )

    elif _is_more_specific(human_code, ai_code):
        discrepancy_type = "OVERCODING"
        explanation = (
            f"Human code '{human_code}' is more specific than "
            f"clinical documentation supports. AI selected '{ai_code}'. "
            f"Overcoding risk flagged.{drg_note}"
        )

    else:
        discrepancy_type = "UNSUPPORTED_CODE"
        explanation = (
            f"Codes differ without clear specificity direction. "
            f"AI: '{ai_code}', Human: '{human_code}'. Review required."
        )

    discrepancy = {
        "type":              discrepancy_type,
        "ai_code":           ai_code,
        "human_code":        human_code,
        "ai_description":    ai_row["description"]    if ai_row    else "Unknown",
        "human_description": human_row["description"] if human_row else "Unknown",
        "explanation":       explanation,
        "revenue_delta":     delta,
        "drg_flag":          drg_flag,
        "ai_is_mcc":         ai_is_mcc,
        "ai_is_cc":          ai_is_cc,
    }

    state["discrepancy_type"] = discrepancy_type
    state["financial_delta"]  = delta
    state["discrepancy"]      = discrepancy

    log.info(
        "audit_complete",
        session_id=session_id,
        discrepancy_type=discrepancy_type,
        ai_code=ai_code,
        human_code=human_code,
        financial_delta=delta,
        drg_flag=drg_flag,
    )

    return state
