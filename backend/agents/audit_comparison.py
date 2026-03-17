"""
This agent compares the AI's coding result with a human coder's input.
It's the core of the audit functionality, calculating financial impact and
identifying compliance risks like undercoding or overcoding.
"""
from agents.graph import CodingState
from agents.node_runner import safe_node
from database import select_one
from logger import get_logger

log = get_logger(__name__)


def _is_more_specific(ai_code: str, human_code: str) -> bool:
    """
    Checks if ai_code is more specific than human_code.
    In ICD-10, a longer code = more detailed — BUT only within the same 3-character
    category prefix. E11.22 > E11.9 (same category, more specific). E11.22 is NOT
    more specific than J18.9 — they are different categories entirely.
    """
    # Different ICD-10 categories — cannot determine specificity by length
    if ai_code[:3] != human_code[:3]:
        return False
    return len(ai_code) > len(human_code)


@safe_node("audit_comparison")
async def audit_comparison_node(state: CodingState) -> CodingState:
    # This is the main function for the audit comparison node in our LangGraph pipeline.
    # It takes the final state from the previous nodes and adds the audit results.
    session_id  = str(state.get("session_id", ""))
    ai_code     = state.get("final_icd_code", "UNKNOWN")
    human_code  = state.get("human_icd_code")

    # If no human-provided code exists, there's nothing to compare.
    # We'll skip the audit and move to the next step.
    if not human_code:
        state["discrepancy_type"] = "NO_COMPARISON"
        state["financial_delta"]  = 0.0
        state["discrepancy"]      = None
        log.info("audit_skipped", session_id=session_id, reason="no human_icd_code")
        return state

    # First, we need to get the details for the AI's suggested code from our database.
    ai_row = await select_one(
        table="icd_codes",
        query="code,description,base_reimbursement,is_cc,is_mcc",
        filters={"code": f"eq.{ai_code}"},
    )

    # Next, we do the same for the human's code. This might fail if the code is invalid.
    human_row = await select_one(
        table="icd_codes",
        query="code,description,base_reimbursement,is_cc,is_mcc",
        filters={"code": f"eq.{human_code}"},
    )

    ai_reimb    = float(ai_row["base_reimbursement"])    if ai_row    else 0.0
    human_reimb = float(human_row["base_reimbursement"]) if human_row else 0.0
    delta       = round(ai_reimb - human_reimb, 2)

    # Here we check for gaps in capturing complications (CC) or major complications (MCC).
    # This is a critical part of revenue integrity, as missing these can lead to underpayment.
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

    # Fetch evidence snippets for both AI and human codes
    ai_evidence = await fetch_evidence_snippet(ai_code)
    human_evidence = await fetch_evidence_snippet(human_code)

    # Now we can determine the overall type of discrepancy and create a clear explanation.
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
        discrepancy_type = "CODE_DIVERGENCE"
        explanation = (
            f"AI code '{ai_code}' and human code '{human_code}' belong to different "
            f"ICD-10 categories — neither is a specificity improvement of the other. "
            f"This may indicate a fundamentally different clinical interpretation. "
            f"Manual review required.{drg_note}"
        )

    # We'll bundle all the audit findings into a single dictionary for clarity.
    discrepancy = {
        "type":              discrepancy_type,
        "ai_code":           ai_code,
        "human_code":        human_code,
        "ai_description":    ai_row["description"]    if ai_row    else "Unknown",
        "human_description": human_row["description"] if human_row else "Unknown",
        "ai_evidence":       ai_evidence,
        "human_evidence":    human_evidence,
        "explanation":       explanation,
        "revenue_delta":     delta,
        "drg_flag":          drg_flag,
    }

    # Finally, update the main state object with our results.
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


async def fetch_evidence_snippet(icd_code: str) -> str:
    """
    Fetch supporting evidence for the given ICD code from the database.
    """
    evidence_row = await select_one(
        table="icd_evidence",
        query="snippet",
        filters={"icd_code": f"eq.{icd_code}"},
    )
    return evidence_row["snippet"] if evidence_row else "No evidence available."
