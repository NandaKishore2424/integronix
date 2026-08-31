"""
agents/financial_calculator.py — Revenue Cycle Management (RCM) Financial Engine

This is the final node in the Integronix LangGraph pipeline. It runs AFTER
the CPT resolver has identified the billing codes. Its job is to:
  1. Look up the hospital's specific pricing multiplier from org_settings.
  2. Apply that multiplier to each resolved CPT base price.
  3. Calculate the total estimated gross hospital revenue for this patient visit.
  4. Falls back to ICD code base_reimbursement values when CPT codes are absent.
"""
from supabase import create_client, Client
from agents.graph import CodingState
from agents.node_runner import safe_node
from logger import get_logger
from config import settings

log = get_logger(__name__)

# Default multiplier if org setting cannot be retrieved — represents the national
# CMS average, so we never return inflated numbers in a failure scenario.
DEFAULT_MULTIPLIER = 1.0


def _get_org_multiplier(supabase: Client, org_id: str) -> float:
    """
    Fetch the cpt_pricing_multiplier for a given org from org_settings.
    Falls back to DEFAULT_MULTIPLIER (1.0) on any failure.
    """
    try:
        response = (
            supabase.table("org_settings")
            .select("cpt_pricing_multiplier")
            .eq("organization_id", org_id)
            .limit(1)
            .execute()
        )
        if response.data and len(response.data) > 0:
            return float(response.data[0]["cpt_pricing_multiplier"])
    except Exception as e:
        log.warning("multiplier_fetch_failed", org_id=org_id, error=str(e))
    return DEFAULT_MULTIPLIER


@safe_node("financial_calc")
async def financial_calculator_node(state: CodingState) -> CodingState:
    """
    Applies the hospital-specific pricing multiplier to all resolved CPT codes
    and computes the total estimated gross revenue for this patient encounter.
    """
    session_id = str(state.get("session_id", ""))
    cpt_codes = state.get("cpt_codes", [])

    # If CPT resolver found nothing, fall back to ICD code base_reimbursement values.
    # This ensures the claim always carries a non-zero billed amount for coded visits.
    if not cpt_codes:
        icd_codes = state.get("icd_codes", [])
        icd_total = round(sum(float(c.get("base_reimbursement", 0)) for c in icd_codes), 2)
        log.info("financial_calc_icd_fallback", session_id=session_id, icd_total=icd_total)
        state["financial_summary"] = {
            "total_estimated_revenue": icd_total,
            "pricing_multiplier": DEFAULT_MULTIPLIER,
            "line_items": []
        }
        return state

    # Retrieve the org multiplier from the database.
    #
    # When no org_id is present we fall back to DEFAULT_MULTIPLIER, never to
    # another organization's rate. An earlier version read the first row of
    # org_settings here, which silently priced one hospital's encounter using
    # a different tenant's multiplier — wrong money, and a tenant boundary
    # crossing, with nothing in the output to indicate it had happened.
    org_id = state.get("org_id")
    if org_id:
        supabase: Client = create_client(
            settings.supabase_url,
            settings.supabase_service_key or settings.supabase_anon_key,
        )
        multiplier = _get_org_multiplier(supabase, org_id)
    else:
        log.warning(
            "financial_calc_no_org_using_default",
            session_id=session_id,
            multiplier=DEFAULT_MULTIPLIER,
        )
        multiplier = DEFAULT_MULTIPLIER

    log.info("financial_calc_started", session_id=session_id, multiplier=multiplier, cpt_count=len(cpt_codes))

    # Apply the multiplier to each CPT code to produce the hospital-specific charge
    line_items = []
    total = 0.0

    for cpt in cpt_codes:
        base = float(cpt.get("base_price", 0.0))
        gross_charge = round(base * multiplier, 2)
        total += gross_charge

        line_items.append({
            "code":          cpt.get("code"),
            "description":   cpt.get("description"),
            "type":          cpt.get("type"),
            "base_price":    base,
            "multiplier":    multiplier,
            "gross_charge":  gross_charge,
            "confidence":    cpt.get("confidence"),
            "original_text": cpt.get("original_text"),
        })

    financial_summary = {
        "total_estimated_revenue": round(total, 2),
        "pricing_multiplier":      multiplier,
        "line_items":              line_items
    }

    # Write the enriched codes and financial summary back to state
    state["cpt_codes"] = line_items
    state["financial_summary"] = financial_summary

    log.info(
        "financial_calc_complete",
        session_id=session_id,
        total_revenue=total,
        multiplier=multiplier
    )
    return state
