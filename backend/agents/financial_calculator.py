"""
agents/financial_calculator.py — Revenue Cycle Management (RCM) Financial Engine

This is the final node in the Integronix LangGraph pipeline. It runs AFTER
the CPT resolver has identified the billing codes. Its job is to:
  1. Look up the hospital's specific pricing multiplier from org_settings.
  2. Apply that multiplier to each resolved CPT base price.
  3. Calculate the total estimated gross hospital revenue for this patient visit.
  4. Falls back to ICD code base_reimbursement values when CPT codes are absent.

Money is computed in Decimal and quantized to cents once per amount — float
arithmetic drifts, and these numbers flow into EDI 837 claims that must
reconcile exactly. JSON-facing values are converted back to float at the edge.
"""
from decimal import Decimal, ROUND_HALF_UP

from agents.graph import CodingState
from agents.node_runner import safe_node
from database import select_one
from logger import get_logger

log = get_logger(__name__)

# Default multiplier if org setting cannot be retrieved — represents the national
# CMS average, so we never return inflated numbers in a failure scenario.
DEFAULT_MULTIPLIER = Decimal("1.0")
CENT = Decimal("0.01")


def _cents(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(CENT, rounding=ROUND_HALF_UP)


async def _get_org_multiplier(org_id: str) -> Decimal:
    """
    Fetch the cpt_pricing_multiplier for a given org from org_settings.
    Falls back to DEFAULT_MULTIPLIER (1.0) on any failure.

    Uses the shared async data layer — this node used to build a synchronous
    supabase client per request and call it inside async code, which blocked
    the event loop for every other in-flight request while the query ran.
    """
    try:
        row = await select_one(
            "org_settings",
            query="cpt_pricing_multiplier",
            filters={"organization_id": f"eq.{org_id}"},
        )
        if row and row.get("cpt_pricing_multiplier") is not None:
            return Decimal(str(row["cpt_pricing_multiplier"]))
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
        icd_total = _cents(sum(
            (Decimal(str(c.get("base_reimbursement") or 0)) for c in icd_codes),
            Decimal("0"),
        ))
        log.info("financial_calc_icd_fallback", session_id=session_id, icd_total=float(icd_total))
        state["financial_summary"] = {
            "total_estimated_revenue": float(icd_total),
            "pricing_multiplier": float(DEFAULT_MULTIPLIER),
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
        multiplier = await _get_org_multiplier(org_id)
    else:
        log.warning(
            "financial_calc_no_org_using_default",
            session_id=session_id,
            multiplier=float(DEFAULT_MULTIPLIER),
        )
        multiplier = DEFAULT_MULTIPLIER

    log.info("financial_calc_started", session_id=session_id,
             multiplier=float(multiplier), cpt_count=len(cpt_codes))

    # Apply the multiplier to each CPT code to produce the hospital-specific
    # charge. Each line's gross charge is quantized to cents, and the TOTAL is
    # the sum of those quantized lines — never a separately-rounded figure —
    # so the total always equals the sum of the line items on the claim.
    line_items = []
    total = Decimal("0")

    for cpt in cpt_codes:
        base = _cents(cpt.get("base_price"))
        gross_charge = _cents(base * multiplier)
        total += gross_charge

        line_items.append({
            "code":          cpt.get("code"),
            "description":   cpt.get("description"),
            "type":          cpt.get("type"),
            "base_price":    float(base),
            "multiplier":    float(multiplier),
            "gross_charge":  float(gross_charge),
            "confidence":    cpt.get("confidence"),
            "original_text": cpt.get("original_text"),
        })

    financial_summary = {
        "total_estimated_revenue": float(total),
        "pricing_multiplier":      float(multiplier),
        "line_items":              line_items
    }

    # Write the enriched codes and financial summary back to state
    state["cpt_codes"] = line_items
    state["financial_summary"] = financial_summary

    log.info(
        "financial_calc_complete",
        session_id=session_id,
        total_revenue=float(total),
        multiplier=float(multiplier)
    )
    return state
