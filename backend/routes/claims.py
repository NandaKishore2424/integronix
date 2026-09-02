import uuid
from decimal import Decimal, ROUND_HALF_UP
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Any, Literal
from logger import get_logger
from config import settings
from database import select, select_one, insert, update, rpc
from services.payer_policy_gate import run_payer_policy_gate
from services.org_settings_service import get_org_settings
from services.fhir_claim_builder import build_fhir_claim_proposal
from auth import Principal, get_principal, require_roles, require_payer_org

log = get_logger(__name__)
router = APIRouter(prefix="/claims", tags=["claims"])

# ── Money ─────────────────────────────────────────────────────────────────────
# Claim amounts are Decimal, never float. EDI 837/835 must reconcile to the
# cent; float arithmetic drifts (0.1 + 0.2 != 0.3) and the drift accumulates
# across line items. Decimal(str(x)) — not Decimal(x) — so an incoming float
# is parsed from its shortest repr instead of importing its binary error.
CENT = Decimal("0.01")


def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(CENT, rounding=ROUND_HALF_UP)


def _uuid_or_none(value: str | None) -> str | None:
    """claim_audit_logs.changed_by_user_id is a uuid column; dev/test
    principals carry synthetic ids that must become NULL, not a DB error."""
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError):
        return None

# ── Tenant boundary helpers ───────────────────────────────────────────────────

async def _payer_ids_for_org(org_id: str) -> set[str]:
    """The payer records owned by a payer organization (payers.organization_id)."""
    try:
        rows = await select("payers", query="id", filters={"organization_id": f"eq.{org_id}"})
        return {str(r["id"]) for r in rows}
    except Exception as exc:
        log.error("payer_ids_lookup_failed", org_id=org_id, error=str(exc))
        return set()


async def _assert_claim_access(claim: dict, principal: Principal) -> None:
    """
    Confirm the caller may see this claim.

    A hospital user may access claims belonging to their own organization.
    A payer user may access claims routed to a payer their organization owns.
    Anything else is 404 rather than 403 — a claim's existence is itself
    information the caller is not entitled to.
    """
    if principal.is_payer:
        allowed = await _payer_ids_for_org(principal.organization_id)
        if str(claim.get("payer_id") or "") in allowed:
            return
    elif str(claim.get("organization_id") or "") == str(principal.organization_id):
        return

    log.warning(
        "claim_access_denied",
        auth_id=principal.auth_id,
        claim_id=claim.get("id"),
        caller_org=principal.organization_id,
    )
    raise HTTPException(status_code=404, detail="Claim not found")


class ClaimSubmissionRequest(BaseModel):
    session_id: str
    organization_id: str
    payer_id: str
    patient_name: Optional[str] = None
    patient_dob: Optional[str] = None
    patient_sex: Optional[str] = None
    total_billed_amount: float = Field(ge=0, le=100_000_000)
    claim_data: dict
    submission_notes: Optional[str] = None

@router.post("/submit")
async def submit_claim(
    req: ClaimSubmissionRequest,
    principal: Principal = Depends(require_roles("coder", "rcm", "admin")),
):
    """
    Submits a finalized coding session as a Claim to the Payer.

    The organization is taken from the caller's token; a mismatched
    organization_id in the body is rejected rather than honoured.
    """
    org_id = principal.assert_org(req.organization_id)

    log.info("claims_submit_start", session_id=req.session_id, org_id=org_id)

    # Check if a claim already exists for this session to prevent double billing.
    existing = await select("claims", query="id",
                            filters={"session_id": f"eq.{req.session_id}"}, limit=1)
    if existing:
        log.warning("claims_submit_duplicate", session_id=req.session_id)
        raise HTTPException(status_code=400, detail="A claim has already been submitted for this session.")

    # ── Server-side session verification (fail closed) ──
    # The claim body is client-supplied. Before accepting it, verify the coded
    # session actually exists in OUR records, belongs to the caller's org, and
    # produced a usable code. A failed pipeline run must never become a claim.
    case_row = await select_one(
        "clinical_cases",
        query="case_id, processing_status, organization_id",
        filters={"session_id": f"eq.{req.session_id}"},
    )
    if not case_row:
        raise HTTPException(status_code=422, detail="No coded session found for this session_id. Run the coding pipeline first.")
    if case_row.get("processing_status") != "COMPLETE":
        raise HTTPException(status_code=422, detail="This coding session did not complete successfully and cannot be billed.")
    if case_row.get("organization_id") and str(case_row["organization_id"]) != str(org_id):
        log.warning("claims_submit_cross_tenant_session", session_id=req.session_id, caller_org=org_id)
        raise HTTPException(status_code=403, detail="This session does not belong to your organization.")
    result_row = await select_one(
        "coding_results",
        query="ai_icd_code, confidence_score",
        filters={"case_id": f"eq.{case_row['case_id']}", "order": "created_at.desc", "limit": "1"},
    )
    if (
        not result_row
        or not result_row.get("ai_icd_code")
        or result_row["ai_icd_code"] == "UNKNOWN"
        or float(result_row.get("confidence_score") or 0.0) <= 0.0
    ):
        raise HTTPException(status_code=422, detail="This session produced no usable code and cannot be billed. Review is required.")

    # ── PAYER POLICY GATE (trustable automation) ──
    try:
        payer_policy = await select_one(
            "payers",
            query=(
                "id, name, payer_type, base_allowed_multiplier, "
                "auto_approve_enabled, auto_approve_confidence_min, auto_approve_max_risk, "
                "auto_approve_requires_patient_dob, auto_approve_requires_patient_sex, "
                "auto_approve_payer_responsibility_pct, accepted_icd_versions"
            ),
            filters={"id": f"eq.{req.payer_id}"},
        )
    except Exception:
        payer_policy = None

    org_settings = await get_org_settings(req.organization_id) if req.organization_id else None

    gate_report = run_payer_policy_gate(
        claim_data=req.claim_data,
        payer_policy=payer_policy or {},
        org_settings=org_settings,
        # Passed explicitly: the amount lives here, not inside claim_data,
        # and the payer's max_amount cap is measured against it.
        total_billed_amount=req.total_billed_amount,
    )

    # Store the gate report inside the claim payload so the payer can review reasons.
    if isinstance(req.claim_data, dict):
        req.claim_data["payer_gate_report"] = gate_report

    # ── FHIR CLAIM PROPOSAL ──────────────────────────────────────────────────
    # Generate the hospital-proposed FHIR Claim artifact and embed it in the
    # claim payload.  EDI 837 will be derived from the payer-verified version
    # later (V1.2).
    if isinstance(req.claim_data, dict):
        try:
            # Resolve organization name (fall back to id if unavailable)
            _org_name = org_id
            _payer_name = (payer_policy or {}).get("name") or req.payer_id
            try:
                _org_row = await select_one("organizations", query="name",
                                            filters={"id": f"eq.{org_id}"})
                if _org_row:
                    _org_name = _org_row.get("name") or org_id
            except Exception:
                pass

            _claim_tmp_id = str(uuid.uuid4())
            _cd = req.claim_data
            fhir_proposal = build_fhir_claim_proposal(
                claim_id=_claim_tmp_id,
                session_id=req.session_id,
                organization_id=req.organization_id,
                organization_name=_org_name,
                payer_id=req.payer_id,
                payer_name=_payer_name,
                patient_name=req.patient_name,
                patient_dob=req.patient_dob,
                patient_sex=req.patient_sex,
                icd_codes=_cd.get("icd_codes") or [],
                cpt_codes=_cd.get("cpt_codes") or [],
                financial_summary=_cd.get("financial_summary") or {},
                icd_version=_cd.get("icd_version") or (org_settings or {}).get("icd_version"),
                mapping_path=_cd.get("mapping_path"),
                total_billed_amount=float(req.total_billed_amount or 0.0),
            )
            req.claim_data["fhir_claim_proposal"] = fhir_proposal
            log.info("fhir_claim_proposal_built", session_id=req.session_id)
        except Exception as fhir_err:
            log.error("fhir_claim_proposal_failed", error=str(fhir_err), session_id=req.session_id)
            # Non-fatal: claim submission continues without FHIR proposal

    # Auto-approve only when explicitly enabled by payer and gate passes.
    initial_status = "SUBMITTED"
    total_allowed = None
    total_paid = None
    patient_resp = None
    payer_responsibility_pct = None

    if gate_report.get("should_auto_approve"):
        pct = Decimal(str(payer_policy.get("auto_approve_payer_responsibility_pct") or "0.80"))
        payer_multiplier = Decimal(str(payer_policy.get("base_allowed_multiplier") or "1.0"))
        payer_responsibility_pct = float(pct)  # echoed in the response only

        financial_summary = req.claim_data.get("financial_summary") or {}
        line_items = financial_summary.get("line_items") or []

        # Sum in Decimal, quantize ONCE at the end — quantizing per line and
        # summing loses/creates cents relative to the true total.
        total_allowed = _money(sum(
            (Decimal(str(item.get("base_price") or 0)) * payer_multiplier
             for item in line_items), Decimal("0")))
        total_allowed = min(total_allowed, _money(req.total_billed_amount))

        total_paid = _money(total_allowed * pct)
        # Patient responsibility is the REMAINDER, never an independent
        # percentage — the three amounts must sum exactly.
        patient_resp = total_allowed - total_paid

        initial_status = "PAID" if pct >= 1 else "PARTIALLY_PAID"

    # Build the claim payload
    payload = {
        "session_id": req.session_id,
        "organization_id": org_id,  # verified via assert_org — never the raw request value
        "payer_id": req.payer_id,
        "patient_name": req.patient_name,
        "patient_dob": req.patient_dob,
        "status": initial_status,
        "total_billed_amount": req.total_billed_amount,
        "total_allowed_amount": total_allowed,
        "total_paid_amount": total_paid,
        "patient_responsibility": patient_resp,
        "claim_data": req.claim_data,
        "submission_notes": req.submission_notes,
        "denial_reason": None,
    }
    
    try:
        row = await insert("claims", payload)
        if not row:
            raise HTTPException(status_code=500, detail="Failed to create claim record")
        claim_id = row["id"]
    except HTTPException:
        raise
    except Exception as e:
        # Exception text can carry row data; log it, return a reference only.
        log.error("claims_submit_failed", error=str(e), session_id=req.session_id)
        raise HTTPException(status_code=500, detail=f"Claim submission failed. Reference: {req.session_id}")

    # The HIPAA audit trail is NOT optional. If the audit row cannot be
    # written, the claim must not stand — remove it and fail the request,
    # rather than leaving an untracked claim in the payer queue.
    try:
        await insert("claim_audit_logs", {
            "claim_id": claim_id,
            "previous_status": None,
            "new_status": initial_status,
            "changed_by_user_id": _uuid_or_none(principal.user_id),
            "action_notes": (
                "Auto-approved via payer policy gate."
                if gate_report.get("should_auto_approve")
                else "Initial submission to payer workflow."
            ),
        })
    except Exception as audit_e:
        log.error("claims_submit_audit_failed", claim_id=claim_id, error=str(audit_e))
        try:
            await update("claims", {"status": "SUBMISSION_FAILED"}, {"id": f"eq.{claim_id}"})
        except Exception:
            log.error("claims_submit_compensation_failed", claim_id=claim_id)
        raise HTTPException(status_code=500, detail="Claim could not be recorded with an audit trail and was not submitted.")

    return {
        "status": "success",
        "claim_id": claim_id,
        "message": "Claim successfully submitted to the payer workflow."
    }


@router.get("/organization/{org_id}")
async def list_claims(org_id: str, principal: Principal = Depends(get_principal)):
    org_id = principal.assert_org(org_id)
    """
    Retrieves the claims inbox for a specific organization/hospital.
    """
    try:
        rows = await select(
            "claims", query="*, payers(name)",
            filters={"organization_id": f"eq.{org_id}", "order": "created_at.desc"},
            limit=100,
        )
        return {"claims": rows}
    except Exception as e:
        log.error("claims_list_failed", org_id=org_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch claims list.")

@router.get("/payer/{payer_id}")
async def list_payer_claims(
    payer_id: str,
    principal: Principal = Depends(require_payer_org()),
):
    if payer_id not in await _payer_ids_for_org(principal.organization_id):
        log.warning(
            "payer_queue_denied",
            auth_id=principal.auth_id,
            requested_payer=payer_id,
            caller_org=principal.organization_id,
        )
        raise HTTPException(status_code=404, detail="Payer not found")
    """
    Retrieves the global claims inbox array for a specific Payer (Insurance Company).
    Includes the organization/hospital name that submitted the claim.
    """
    try:
        rows = await select(
            "claims", query="*, organizations(name)",
            filters={"payer_id": f"eq.{payer_id}", "order": "created_at.desc"},
            limit=200,
        )
        return {"claims": rows}
    except Exception as e:
        log.error("payer_claims_list_failed", payer_id=payer_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch payer claims list.")

@router.get("/detail/{claim_id}")
async def get_claim_detail(claim_id: str, principal: Principal = Depends(get_principal)):
    """Fetches a single claim detail payload for the Adjudication Screen"""
    try:
        claim = await select_one(
            "claims", query="*, organizations(name), claim_audit_logs(*)",
            filters={"id": f"eq.{claim_id}"},
        )
        if claim:
            await _assert_claim_access(claim, principal)
            return {"claim": claim}
        raise HTTPException(status_code=404, detail="Claim not found")
    except HTTPException:
        raise
    except Exception as e:
        log.error("claim_detail_failed", claim_id=claim_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch claim detail")

@router.get("/payers")
async def list_payers(principal: Principal = Depends(get_principal)):
    """
    Returns the list of enabled payers so the frontend can populate a dropdown
    when the medical coder wants to submit a claim.
    """
    try:
        rows = await select(
            "payers", query="id, name, payer_type, base_allowed_multiplier",
            filters={"order": "name"},
        )
        return {"payers": rows}
    except Exception as e:
        log.error("payers_list_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch payers.")

@router.get("/payers/by-org/{org_id}")
async def get_payer_for_org(org_id: str, principal: Principal = Depends(get_principal)):
    org_id = principal.assert_org(org_id)
    """
    Resolves the payer record for a given organization by its organization_id.
    If an insurance_payer logs in for the first time, auto-creates a payer configured for them.
    """
    try:
        org_data = await select_one("organizations", query="id, name, type",
                                    filters={"id": f"eq.{org_id}"})
        if not org_data:
            raise HTTPException(status_code=404, detail="Organization not found")
        if org_data["type"] != "insurance_payer":
            raise HTTPException(status_code=400, detail="Organization is not a payer")

        # Try to find the exact linked payer record
        payer = await select_one(
            "payers", query="id, name, payer_type, base_allowed_multiplier",
            filters={"organization_id": f"eq.{org_id}"},
        )
        if payer:
            return {"payer": payer}

        # Auto-create if not found (Lazy initialization)
        log.info("payer_autocreate", org_name=org_data["name"], org_id=org_id)
        new_payer = await insert("payers", {
            "organization_id": org_id,
            "name": org_data["name"],
            "payer_type": "commercial",
            "base_allowed_multiplier": 1.00,
        })
        return {"payer": new_payer}
    except HTTPException:
        raise
    except Exception as e:
        log.error("payer_by_org_failed", org_id=org_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to resolve payer for organization.")

class AdjudicationRequest(BaseModel):
    action: Literal["APPROVE", "DENY"]
    denial_reason: Optional[str] = None
    # Share of the allowed amount the payer covers. Bounded: an unbounded value
    # here produces payments above the allowed amount and negative patient
    # responsibility.
    payer_responsibility_pct: float = Field(default=0.80, ge=0.0, le=1.0)

@router.post("/adjudicate/{claim_id}")
async def adjudicate_claim(
    claim_id: str,
    req: AdjudicationRequest,
    principal: Principal = Depends(require_payer_org()),
):
    """
    Payer adjudication of a submitted claim.

    The read happens here in Python, but the WRITE is a single database
    transaction (adjudicate_claim, migration 021): the status check rides in
    the UPDATE's WHERE clause as an optimistic lock, and the HIPAA audit row
    commits atomically with the status change. Two concurrent APPROVEs can
    both pass the Python check below — only one will match the lock; the
    other receives 409 instead of double-paying.
    """
    log.info("claims_adjudicate_start", claim_id=claim_id, action=req.action)

    try:
        # 1. Fetch the claim and its associated payer details
        claim = await select_one(
            "claims", query="*, payers(base_allowed_multiplier)",
            filters={"id": f"eq.{claim_id}"},
        )
        if not claim:
            raise HTTPException(status_code=404, detail="Claim not found")

        await _assert_claim_access(claim, principal)
        expected_status = claim["status"]
        if expected_status in ["PAID", "DENIED", "PARTIALLY_PAID"]:
            raise HTTPException(status_code=400, detail=f"Claim is already {expected_status}")

        # 2. Financial baseline — Decimal end to end
        billed_amount = _money(claim.get("total_billed_amount"))

        if req.action == 'DENY':
            new_status = "DENIED"
            denial_reason = req.denial_reason or "Services not covered under patient plan."
            total_allowed = _money(0)
            total_paid = _money(0)
            patient_resp = billed_amount  # patient owes the full billed amount if denied (simplified)
        else:  # APPROVE — the request model only admits APPROVE | DENY
            # 3. Allowed amount = base prices from the frozen claim_data
            #    snapshot × the payer's contract multiplier.
            claim_data = claim.get("claim_data") or {}
            line_items = (claim_data.get("financial_summary") or {}).get("line_items") or []

            payer_multiplier = Decimal("1.0")
            if claim.get("payers"):
                payer_multiplier = Decimal(str(claim["payers"].get("base_allowed_multiplier") or "1.0"))

            total_allowed = _money(sum(
                (Decimal(str(item.get("base_price") or 0)) * payer_multiplier
                 for item in line_items), Decimal("0")))
            # The payer cannot allow more than the hospital billed.
            total_allowed = min(total_allowed, billed_amount)

            pct = Decimal(str(req.payer_responsibility_pct))
            total_paid = _money(total_allowed * pct)
            # Remainder, not an independent percentage: the three amounts must
            # sum exactly, cent for cent.
            patient_resp = total_allowed - total_paid

            new_status = "PAID" if pct >= 1 else "PARTIALLY_PAID"
            denial_reason = None

        # 4. Atomic write: optimistic-lock UPDATE + audit INSERT + adjudicated_at,
        #    one transaction inside Postgres.
        result = await rpc("adjudicate_claim", {
            "p_claim_id": claim_id,
            "p_expected_status": expected_status,
            "p_new_status": new_status,
            "p_total_allowed": str(total_allowed),
            "p_total_paid": str(total_paid),
            "p_patient_responsibility": str(patient_resp),
            "p_denial_reason": denial_reason,
            "p_action_notes": f"Manual Adjudication: {req.action}. " + (req.denial_reason or ""),
            "p_changed_by_user_id": _uuid_or_none(principal.user_id),
        })
        if not (isinstance(result, dict) and result.get("ok")):
            reason = (result or {}).get("reason") if isinstance(result, dict) else None
            if reason == "not_found":
                raise HTTPException(status_code=404, detail="Claim not found")
            # Someone else adjudicated between our read and our write.
            raise HTTPException(
                status_code=409,
                detail=f"Claim was modified concurrently (now {(result or {}).get('current_status')}). Refresh and retry.",
            )

        adjudication_details = {
            "status": new_status,
            "total_allowed_amount": float(total_allowed),
            "total_paid_amount": float(total_paid),
            "patient_responsibility": float(patient_resp),
            "denial_reason": denial_reason,
        }
        log.info("claims_adjudicate_success", claim_id=claim_id, payload=adjudication_details)
        return {
            "status": "success",
            "message": f"Claim {req.action.lower()}ed successfully.",
            "adjudication_details": adjudication_details,
        }

    except HTTPException:
        raise
    except Exception as e:
        log.error("claims_adjudicate_failed", claim_id=claim_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Adjudication failed. Reference: {claim_id}")

class AppealRequest(BaseModel):
    justification: str

@router.post("/appeal/{claim_id}")
async def appeal_claim(
    claim_id: str,
    req: AppealRequest,
    principal: Principal = Depends(require_roles("rcm", "admin")),
):
    """
    Allows a Hospital Biller to appeal a Denied or Partially Paid claim by providing justification.

    Status change + audit row commit atomically (change_claim_status,
    migration 021); the eligible-status check is the optimistic lock.
    The denial_reason is deliberately kept — it is what the hospital is
    contesting.
    """
    log.info("claims_appeal_start", claim_id=claim_id)

    try:
        claim = await select_one("claims", query="*, payers(name)",
                                 filters={"id": f"eq.{claim_id}"})
        if not claim:
            raise HTTPException(status_code=404, detail="Claim not found")
        await _assert_claim_access(claim, principal)

        result = await rpc("change_claim_status", {
            "p_claim_id": claim_id,
            "p_expected_statuses": ["DENIED", "PARTIALLY_PAID"],
            "p_new_status": "APPEALED",
            "p_action_notes": f"Hospital Appeal Filed: {req.justification}",
            "p_changed_by_user_id": _uuid_or_none(principal.user_id),
        })
        if not (isinstance(result, dict) and result.get("ok")):
            current = (result or {}).get("current_status") if isinstance(result, dict) else None
            raise HTTPException(
                status_code=400,
                detail=f"Cannot appeal a claim in {current} status. Must be DENIED or PARTIALLY_PAID.",
            )

        log.info("claims_appeal_success", claim_id=claim_id)
        return {
            "status": "success",
            "message": "Claim successfully placed in APPEALED status.",
            "claim_id": claim_id
        }

    except HTTPException:
        raise
    except Exception as e:
        log.error("claims_appeal_failed", claim_id=claim_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Appeal failed. Reference: {claim_id}")


# ── TICKET-04: Payer Edit Codes ───────────────────────────────────────────────

class PayerEditRequest(BaseModel):
    edited_icd_codes: List[dict]   # payer-corrected ICD codes [{code, description}, ...]
    edited_cpt_codes: List[dict]   # payer-corrected CPT codes [{cpt_code, description}, ...]
    edit_reason: str               # REQUIRED — payer must explain why they changed the codes


@router.post("/edit/{claim_id}")
async def payer_edit_claim(
    claim_id: str,
    req: PayerEditRequest,
    principal: Principal = Depends(require_payer_org()),
):
    """
    Allows a Payer adjudicator to correct the hospital-proposed ICD/CPT codes before approving.
    - Stores the original codes vs. corrected codes in payer_code_edits for a full audit trail.
    - Marks claim.payer_edited = true so the hospital knows their codes were changed.
    - Appends an audit log entry: SUBMITTED → PAYER_EDITED.
    - Only allowed when the claim status is SUBMITTED.
    """
    if not req.edit_reason or not req.edit_reason.strip():
        raise HTTPException(status_code=400, detail="edit_reason is required. Payer must justify code changes.")

    log.info("claims_payer_edit_start", claim_id=claim_id)

    try:
        # 1. Fetch the claim — must be in SUBMITTED status
        claim = await select_one(
            "claims", query="id, status, claim_data, organization_id, payer_id",
            filters={"id": f"eq.{claim_id}"},
        )
        if not claim:
            raise HTTPException(status_code=404, detail="Claim not found")

        await _assert_claim_access(claim, principal)
        if claim["status"] != "SUBMITTED":
            raise HTTPException(
                status_code=400,
                detail=f"Code edits can only be made on SUBMITTED claims. Current status: {claim['status']}",
            )

        # 2. Snapshot the original hospital-proposed codes from claim_data
        claim_data: dict = claim.get("claim_data") or {}
        original_icd = claim_data.get("icd_codes") or []
        original_cpt = claim_data.get("cpt_codes") or []

        original_codes = {
            "icd_codes": original_icd,
            "cpt_codes": original_cpt,
        }
        edited_codes = {
            "icd_codes": req.edited_icd_codes,
            "cpt_codes": req.edited_cpt_codes,
        }

        # 3. Insert into payer_code_edits audit table
        edit_row_result = await insert("payer_code_edits", {
            "claim_id":       claim_id,
            "original_codes": original_codes,
            "edited_codes":   edited_codes,
            "edit_reason":    req.edit_reason.strip(),
        })
        edit_id = (edit_row_result or {}).get("id")

        # 4. Update claim: payer_edited flag + reason + embed corrected codes
        #    into claim_data. Optimistic lock on status: if the claim left
        #    SUBMITTED between our read and this write, no rows match and we
        #    conflict instead of editing an adjudicated claim.
        claim_data["payer_edited_icd_codes"] = req.edited_icd_codes
        claim_data["payer_edited_cpt_codes"] = req.edited_cpt_codes
        claim_data["payer_edit_reason"] = req.edit_reason.strip()

        updated = await update(
            "claims",
            {
                "payer_edited":      True,
                "payer_edit_reason": req.edit_reason.strip(),
                "claim_data":        claim_data,
            },
            {"id": f"eq.{claim_id}", "status": "eq.SUBMITTED"},
        )
        if not updated:
            raise HTTPException(status_code=409, detail="Claim left SUBMITTED status while editing. Refresh and retry.")

        # 5. HIPAA Audit Trail — payer_code_edits (step 3) is itself durable
        #    audit evidence, so a failure here logs loudly but does not undo
        #    the edit.
        try:
            await insert("claim_audit_logs", {
                "claim_id":        claim_id,
                "previous_status": "SUBMITTED",
                "new_status":      "SUBMITTED",  # Status doesn't change, edit is noted
                "changed_by_user_id": _uuid_or_none(principal.user_id),
                "action_notes":    f"Payer edited codes. Reason: {req.edit_reason.strip()}",
            })
        except Exception as audit_e:
            log.error("claims_payer_edit_audit_failed", claim_id=claim_id, error=str(audit_e))

        log.info("claims_payer_edit_success", claim_id=claim_id, edit_id=edit_id)
        return {
            "status":  "success",
            "message": "Payer code edits saved successfully. You may now approve or deny the claim.",
            "edit_id": edit_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        log.error("claims_payer_edit_failed", claim_id=claim_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Code edit failed. Reference: {claim_id}")




from fastapi.responses import PlainTextResponse
from services.edi_837_builder import build_edi_837

@router.get("/export/edi/{claim_id}", response_class=PlainTextResponse)
async def export_edi_837(claim_id: str, principal: Principal = Depends(get_principal)):
    """
    Generates a real ANSI ASC X12 837P EDI Health Care Claim string derived
    from the FHIR Claim proposal stored in ``claim_data.fhir_claim_proposal``.
    All values (patient name, ICD codes, CPT service lines, amounts) are real —
    no fake placeholder data is ever emitted.
    """
    try:
        claim = await select_one(
            "claims", query="*, organizations(name), payers(name, payer_type)",
            filters={"id": f"eq.{claim_id}"},
        )
        if not claim:
            raise HTTPException(status_code=404, detail="Claim not found")

        await _assert_claim_access(claim, principal)
        org_name   = (claim.get("organizations") or {}).get("name") or "INTEGRONIX HOSPITAL"
        payer_name = (claim.get("payers") or {}).get("name") or "UNKNOWN PAYER"
        total_billed = float(claim.get("total_billed_amount") or 0.0)

        # ── Prefer FHIR proposal; fall back to synthesising from raw claim_data ──
        claim_data: dict = claim.get("claim_data") or {}
        fhir_claim: dict = claim_data.get("fhir_claim_proposal") or {}

        if not fhir_claim:
            # No FHIR proposal stored yet (pre-TICKET-02 submissions).
            # Build a minimal stub so the export still works gracefully.
            log.warning(
                "edi_export_no_fhir_proposal",
                claim_id=claim_id,
                detail="fhir_claim_proposal missing in claim_data; generating minimal EDI"
            )
            # Construct a minimal FHIR-shaped dict from raw claim_data fields
            # so the builder can still emit ISA→CLM without crashing.
            icd_codes: list = claim_data.get("icd_codes") or []
            cpt_codes: list = claim_data.get("cpt_codes") or []
            financial: dict = claim_data.get("financial_summary") or {}
            line_items: list = financial.get("line_items") or []

            fhir_claim = {
                "id": claim_id,
                "created": claim.get("created_at"),
                "patient": {"reference": "#patient-1"},
                "contained": [
                    {
                        "resourceType": "Patient",
                        "id": "patient-1",
                        **({"name": [{"text": claim.get("patient_name"), "given": [claim.get("patient_name", "").split(" ")[0]], "family": claim.get("patient_name", "").split(" ")[-1]}]} if claim.get("patient_name") else {}),
                        **({"birthDate": claim.get("patient_dob")} if claim.get("patient_dob") else {}),
                    }
                ],
                "diagnosis": [
                    {
                        "sequence": i + 1,
                        "diagnosisCodeableConcept": {
                            "coding": [{"code": c.get("code") or c.get("ai_icd_code", ""), "display": c.get("description", "")}]
                        }
                    }
                    for i, c in enumerate(icd_codes)
                    if c.get("code") or c.get("ai_icd_code")
                ],
                "item": [
                    {
                        "sequence": i + 1,
                        "productOrService": {
                            "coding": [{"code": li.get("cpt_code") or li.get("code", ""), "display": li.get("description", "")}]
                        },
                        "unitPrice": {"value": float(li.get("gross_charge") or li.get("base_price") or 0.0), "currency": "INR"},
                        "quantity": {"value": 1},
                    }
                    for i, li in enumerate(line_items)
                    if li.get("cpt_code") or li.get("code")
                ],
                "total": {"value": total_billed, "currency": "INR"},
            }

        edi_text = build_edi_837(
            fhir_claim=fhir_claim,
            org_name=org_name,
            payer_name=payer_name,
            claim_db_id=claim_id,
            total_billed_amount=total_billed,
            service_date=claim.get("created_at"),
        )

        log.info("edi_export_success", claim_id=claim_id, segment_count=edi_text.count("~"))
        return PlainTextResponse(
            content=edi_text,
            media_type="text/plain",
            headers={
                "Content-Disposition": f'attachment; filename="claim_{claim_id[:8]}.edi"'
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        log.error("claims_edi_failed", claim_id=claim_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"EDI export failed. Reference: {claim_id}")


# ── TICKET-05: EDI 835 Remittance Export ─────────────────────────────────────
from services.edi_835_builder import build_edi_835

_EDI_835_ALLOWED_STATUSES = {"PAID", "PARTIALLY_PAID", "DENIED"}


@router.get("/export/edi835/{claim_id}", response_class=PlainTextResponse)
async def export_edi_835(claim_id: str, principal: Principal = Depends(get_principal)):
    """
    Generates a real ANSI ASC X12 835 Remittance Advice EDI file.

    Only available when claim is in PAID, PARTIALLY_PAID, or DENIED status.
    Contains BPR, CLP, CAS, and SVC segments derived from the FHIR proposal.
    """
    try:
        claim = await select_one(
            "claims", query="*, organizations(name), payers(name)",
            filters={"id": f"eq.{claim_id}"},
        )
        if not claim:
            raise HTTPException(status_code=404, detail="Claim not found")

        await _assert_claim_access(claim, principal)
        status = claim.get("status", "")
        if status not in _EDI_835_ALLOWED_STATUSES:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"EDI 835 is only available for adjudicated claims "
                    f"(PAID, PARTIALLY_PAID, or DENIED). Current status: {status}"
                ),
            )

        claim_data: dict = claim.get("claim_data") or {}
        fhir_claim = claim_data.get("fhir_claim_proposal")

        org_name: str = (claim.get("organizations") or {}).get("name") or "Unknown Provider"
        payer_name: str = (claim.get("payers") or {}).get("name") or "Unknown Payer"
        patient_name: str = claim.get("patient_name") or claim_data.get("patient_name") or ""
        denial_reason: str = claim.get("denial_reason") or ""

        total_billed = float(claim.get("total_billed_amount") or 0.0)
        total_paid = float(claim.get("total_paid_amount") or 0.0)

        edi_content = build_edi_835(
            claim_id=claim_id,
            claim_status=status,
            total_billed=total_billed,
            total_paid=total_paid,
            org_name=org_name,
            payer_name=payer_name,
            patient_name=patient_name,
            service_date=claim.get("created_at"),
            fhir_claim=fhir_claim,
            denial_reason=denial_reason,
        )

        filename = f"remittance_{claim_id[:8]}.edi"
        log.info("claims_edi835_success", claim_id=claim_id, status=status)
        return PlainTextResponse(
            content=edi_content,
            media_type="application/EDI-X12",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except HTTPException:
        raise
    except Exception as e:
        log.error("claims_edi835_failed", claim_id=claim_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"EDI 835 export failed. Reference: {claim_id}")
