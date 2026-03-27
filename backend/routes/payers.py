"""
backend/routes/payers.py

TICKET-08: Payer Automation Settings — GET + PUT endpoints.

Allows payer administrators to read and update their organisation's
auto-approval policy and custom rules directly from the dashboard.
"""

from __future__ import annotations

from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from supabase import create_client

from config import settings
from logger import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/payers", tags=["payers"])


# ── helpers ──────────────────────────────────────────────────────────────────

def _sb():
    """Return a service-role Supabase client."""
    return create_client(
        settings.supabase_url,
        settings.supabase_service_key or settings.supabase_anon_key,
    )

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
async def get_payer_settings(payer_id: str) -> PayerSettingsOut:
    """
    Returns the full automation policy for the requested payer organisation.
    """
    sb = _sb()
    try:
        resp = sb.table("payers").select(SETTINGS_SELECT).eq("id", payer_id).limit(1).execute()
    except Exception as exc:
        log.error("payer_settings_fetch_failed", payer_id=payer_id, error=str(exc))
        raise HTTPException(status_code=503, detail="Database error while fetching payer settings.")

    if not resp.data:
        raise HTTPException(status_code=404, detail=f"Payer '{payer_id}' not found.")

    row = resp.data[0]
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
async def update_payer_settings(payer_id: str, body: PayerSettingsIn) -> PayerSettingsOut:
    """
    Persists updated automation policy for a payer.
    Only payer admins should be allowed to call this from the dashboard.
    """
    sb = _sb()

    # Confirm the record exists before patching
    check = sb.table("payers").select("id").eq("id", payer_id).limit(1).execute()
    if not check.data:
        raise HTTPException(status_code=404, detail=f"Payer '{payer_id}' not found.")

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
        sb.table("payers").update(patch).eq("id", payer_id).execute()
    except Exception as exc:
        log.error("payer_settings_update_failed", payer_id=payer_id, error=str(exc))
        raise HTTPException(status_code=503, detail="Database error while saving payer settings.")

    log.info("payer_settings_updated", payer_id=payer_id, auto_approve_enabled=body.auto_approve_enabled)
    # Return the new state
    return await get_payer_settings(payer_id)
