"""
backend/routes/payers.py

TICKET-08: Payer Automation Settings — GET + PUT endpoints.

Allows payer administrators to read and update their organisation's
auto-approval policy and custom rules directly from the dashboard.
"""

from __future__ import annotations

from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from config import settings
from database import select, update
from logger import get_logger

log = get_logger(__name__)
from auth import Principal, get_principal, require_payer_org

router = APIRouter(prefix="/payers", tags=["payers"])


async def _assert_owns_payer(principal: Principal, payer_id: str) -> None:
    """
    A payer organization may only read or modify its own payer record.

    These settings gate auto-approval — confidence floors, risk ceilings, the
    payer responsibility percentage — so write access here is equivalent to
    control over disbursement.
    """
    try:
        rows = await select("payers", query="id", filters={
            "id": f"eq.{payer_id}",
            "organization_id": f"eq.{principal.organization_id}",
        }, limit=1)
        if rows:
            return
    except Exception as exc:
        log.error("payer_ownership_check_failed", payer_id=payer_id, error=str(exc))
        raise HTTPException(status_code=503, detail="Could not verify payer access.")

    log.warning(
        "payer_settings_denied",
        auth_id=principal.auth_id,
        requested_payer=payer_id,
        caller_org=principal.organization_id,
    )
    raise HTTPException(status_code=404, detail=f"Payer '{payer_id}' not found.")


# ── Pydantic models ───────────────────────────────────────────────────────────

class CustomRule(BaseModel):
    rule_type: str = Field(..., description=(
        "One of: max_amount | exclude_cpt_prefix | require_min_age | require_max_age"
    ))
    label: str = Field(..., description="Human-readable label shown in the UI.")
    # Optional fields — only the relevant one is used per rule_type
    threshold: Optional[float] = Field(None, description="INR threshold for max_amount rule.")
    code_prefix: Optional[str] = Field(None, description="CPT code prefix to block (e.g. '274').")
    min_age: Optional[int] = Field(None, description="Minimum patient age for require_min_age rule.")
    max_age: Optional[int] = Field(None, description="Maximum patient age for require_max_age rule.")


class PayerSettingsOut(BaseModel):
    payer_id: str
    auto_approve_enabled: bool
    auto_approve_confidence_min: float
    auto_approve_max_risk: float
    auto_approve_requires_patient_dob: bool
    auto_approve_requires_patient_sex: bool
    auto_approve_payer_responsibility_pct: float
    accepted_icd_versions: List[str]
    auto_approve_custom_rules: List[CustomRule]


class PayerSettingsIn(BaseModel):
    auto_approve_enabled: bool
    auto_approve_confidence_min: float = Field(..., ge=0.0, le=1.0)
    auto_approve_max_risk: float = Field(..., ge=0.0, le=1.0)
    auto_approve_requires_patient_dob: bool
    auto_approve_requires_patient_sex: bool
    auto_approve_payer_responsibility_pct: float = Field(..., ge=0.0, le=1.0)
    accepted_icd_versions: List[str]
    auto_approve_custom_rules: List[CustomRule] = []


# ── routes ────────────────────────────────────────────────────────────────────

SETTINGS_SELECT = (
    "id, auto_approve_enabled, auto_approve_confidence_min, auto_approve_max_risk, "
    "auto_approve_requires_patient_dob, auto_approve_requires_patient_sex, "
    "auto_approve_payer_responsibility_pct, accepted_icd_versions, auto_approve_custom_rules"
)


@router.get("/{payer_id}/settings", response_model=PayerSettingsOut)
async def get_payer_settings(
    payer_id: str,
    principal: Principal = Depends(require_payer_org()),
) -> PayerSettingsOut:
    """
    Returns the full automation policy for the requested payer organisation.
    """
    await _assert_owns_payer(principal, payer_id)
    try:
        rows = await select("payers", query=SETTINGS_SELECT,
                            filters={"id": f"eq.{payer_id}"}, limit=1)
    except Exception as exc:
        log.error("payer_settings_fetch_failed", payer_id=payer_id, error=str(exc))
        raise HTTPException(status_code=503, detail="Database error while fetching payer settings.")

    if not rows:
        raise HTTPException(status_code=404, detail=f"Payer '{payer_id}' not found.")

    row = rows[0]
    return PayerSettingsOut(
        payer_id=row["id"],
        auto_approve_enabled=bool(row.get("auto_approve_enabled", False)),
        auto_approve_confidence_min=float(row.get("auto_approve_confidence_min", 0.80)),
        auto_approve_max_risk=float(row.get("auto_approve_max_risk", 0.35)),
        auto_approve_requires_patient_dob=bool(row.get("auto_approve_requires_patient_dob", True)),
        auto_approve_requires_patient_sex=bool(row.get("auto_approve_requires_patient_sex", True)),
        auto_approve_payer_responsibility_pct=float(row.get("auto_approve_payer_responsibility_pct", 0.80)),
        accepted_icd_versions=row.get("accepted_icd_versions") or ["ICD-10", "ICD-11"],
        auto_approve_custom_rules=[CustomRule(**r) for r in (row.get("auto_approve_custom_rules") or [])],
    )


@router.put("/{payer_id}/settings", response_model=PayerSettingsOut)
async def update_payer_settings(
    payer_id: str,
    body: PayerSettingsIn,
    principal: Principal = Depends(require_payer_org()),
) -> PayerSettingsOut:
    """
    Persists updated automation policy for a payer.
    Only payer admins should be allowed to call this from the dashboard.
    """
    # Confirm the record exists before patching
    await _assert_owns_payer(principal, payer_id)

    patch = {
        "auto_approve_enabled": body.auto_approve_enabled,
        "auto_approve_confidence_min": body.auto_approve_confidence_min,
        "auto_approve_max_risk": body.auto_approve_max_risk,
        "auto_approve_requires_patient_dob": body.auto_approve_requires_patient_dob,
        "auto_approve_requires_patient_sex": body.auto_approve_requires_patient_sex,
        "auto_approve_payer_responsibility_pct": body.auto_approve_payer_responsibility_pct,
        "accepted_icd_versions": body.accepted_icd_versions,
        "auto_approve_custom_rules": [r.model_dump(exclude_none=True) for r in body.auto_approve_custom_rules],
    }

    try:
        updated = await update("payers", patch, {"id": f"eq.{payer_id}"})
        if not updated:
            raise HTTPException(status_code=404, detail=f"Payer '{payer_id}' not found.")
    except HTTPException:
        raise
    except Exception as exc:
        log.error("payer_settings_update_failed", payer_id=payer_id, error=str(exc))
        raise HTTPException(status_code=503, detail="Database error while saving payer settings.")

    log.info("payer_settings_updated", payer_id=payer_id, auto_approve_enabled=body.auto_approve_enabled)
    # Return the new state. principal must be passed explicitly — this is a
    # direct function call, so FastAPI's Depends default would otherwise leak
    # in as a raw Depends object and poison the ownership check.
    return await get_payer_settings(payer_id, principal)
