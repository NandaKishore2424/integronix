import uuid
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional, List, Any
from supabase import create_client, Client
from logger import get_logger
from config import settings
from services.payer_policy_gate import run_payer_policy_gate
from services.org_settings_service import get_org_settings
from services.fhir_claim_builder import build_fhir_claim_proposal

log = get_logger(__name__)
router = APIRouter(prefix="/claims", tags=["claims"])

def get_supabase(authorization: Optional[str] = Header(None)) -> Client:
    """Gets a service-role supabase client to interact with the claims db."""
    url = settings.supabase_url
    key = settings.supabase_service_key or settings.supabase_anon_key
    return create_client(url, key)

class ClaimSubmissionRequest(BaseModel):
    session_id: str
    organization_id: str
    payer_id: str
    patient_name: Optional[str] = None
    patient_dob: Optional[str] = None
    patient_sex: Optional[str] = None
    total_billed_amount: float
    claim_data: dict
    submission_notes: Optional[str] = None

@router.post("/submit")
async def submit_claim(req: ClaimSubmissionRequest):
    """
    Submits a finalized coding session as a Claim to the Payer.
    """
    supabase = get_supabase()
    
    log.info("claims_submit_start", session_id=req.session_id, org_id=req.organization_id)
    
    # Check if a claim already exists for this session to prevent double billing
    try:
        existing = getattr(supabase.table("claims").select("id").eq("session_id", req.session_id).limit(1), "execute")()
        if existing and existing.data and len(existing.data) > 0:
            log.warning("claims_submit_duplicate", session_id=req.session_id)
            raise HTTPException(status_code=400, detail="A claim has already been submitted for this session.")
    except Exception as e:
        # Ignore errors if the table doesn't exist yet / not migrated
        pass

    # ── PAYER POLICY GATE (trustable automation) ──
    try:
        payer_policy_resp = getattr(
            supabase.table("payers")
            .select(
                "id, name, payer_type, base_allowed_multiplier, "
                "auto_approve_enabled, auto_approve_confidence_min, auto_approve_max_risk, "
                "auto_approve_requires_patient_dob, auto_approve_requires_patient_sex, "
                "auto_approve_payer_responsibility_pct, accepted_icd_versions"
            )
            .eq("id", req.payer_id)
            .single(),
            "execute",
        )()
        # Supabase client returns a response object with `.data`
        payer_policy = None
        if payer_policy_resp and getattr(payer_policy_resp, "data", None):
            # `.single()` typically returns an object (not a list), but handle both.
            if isinstance(payer_policy_resp.data, list):
                payer_policy = payer_policy_resp.data[0] if payer_policy_resp.data else None
            else:
                payer_policy = payer_policy_resp.data
    except Exception:
        payer_policy = None

    org_settings = await get_org_settings(req.organization_id) if req.organization_id else None

    gate_report = run_payer_policy_gate(
        claim_data=req.claim_data,
        payer_policy=payer_policy or {},
        org_settings=org_settings,
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
            _org_name_resp = None
            _org_name = req.organization_id
            _payer_name = (payer_policy or {}).get("name") or req.payer_id
            try:
                _org_resp = getattr(
                    supabase.table("organizations").select("name").eq("id", req.organization_id).single(),
                    "execute",
                )()
                if _org_resp and getattr(_org_resp, "data", None):
                    _org_name = _org_resp.data.get("name") or req.organization_id
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
        payer_responsibility_pct = float(payer_policy.get("auto_approve_payer_responsibility_pct") or 0.80)
        payer_multiplier = float(payer_policy.get("base_allowed_multiplier") or 1.0)

        financial_summary = req.claim_data.get("financial_summary") or {}
        line_items = financial_summary.get("line_items") or []

        total_allowed = 0.0
        for item in line_items:
            base = float(item.get("base_price") or 0.0)
            total_allowed += base * payer_multiplier

        total_allowed = round(total_allowed, 2)
        total_allowed = min(total_allowed, float(req.total_billed_amount or 0.0))

        total_paid = round(total_allowed * payer_responsibility_pct, 2)
        patient_resp = round(total_allowed - total_paid, 2)

        initial_status = "PAID" if payer_responsibility_pct >= 1.0 else "PARTIALLY_PAID"

    # Build the claim payload
    payload = {
        "session_id": req.session_id,
        "organization_id": req.organization_id,
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
        # We handle submitted_at via DB trigger or manual insert using string 'now()' isn't always safe natively in python client
        res = getattr(supabase.table("claims").insert(payload), "execute")()
        
        # Manually update the submitted_at timestamp (since we can't use functions in normal insert JSON simply)
        if res and res.data and len(res.data) > 0:
            claim_id = res.data[0]["id"]
            
            # === Insert HIPAA Audit Trail ===
            try:
                audit_log = {
                    "claim_id": claim_id,
                    "previous_status": None,
                    "new_status": initial_status,
                    "action_notes": (
                        "Auto-approved via payer policy gate."
                        if gate_report.get("should_auto_approve")
                        else "Initial submission to payer workflow."
                    ),
                }
                getattr(supabase.table("claim_audit_logs").insert(audit_log), "execute")()
            except Exception as audit_e:
                log.error("claims_submit_audit_failed", error=str(audit_e))

            # To be thoroughly bulletproof on python client version behavior:
            return {
                "status": "success", 
                "claim_id": claim_id, 
                "message": "Claim successfully submitted to the payer workflow."
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to create claim record")
            
    except Exception as e:
        log.error("claims_submit_failed", error=str(e), session_id=req.session_id)
        if hasattr(e, "message"):
            raise HTTPException(status_code=500, detail=str(e.message))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/organization/{org_id}")
async def list_claims(org_id: str):
    """
    Retrieves the claims inbox for a specific organization/hospital.
    """
    supabase = get_supabase()
    
    try:
        # Fetching claims and joining payer name
        res = getattr(supabase.table("claims").select("*, payers(name)").eq("organization_id", org_id).order("created_at", desc=True).limit(100), "execute")()
        
        if res and res.data is not None:
            return {"claims": res.data}
        return {"claims": []}
    except Exception as e:
        log.error("claims_list_failed", org_id=org_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch claims list.")

@router.get("/payer/{payer_id}")
async def list_payer_claims(payer_id: str):
    """
    Retrieves the global claims inbox array for a specific Payer (Insurance Company).
    Includes the organization/hospital name that submitted the claim.
    """
    supabase = get_supabase()
    
    try:
        # Fetching claims and joining organization name to see who billed them
        res = getattr(supabase.table("claims").select("*, organizations(name)").eq("payer_id", payer_id).order("created_at", desc=True).limit(200), "execute")()
        
        if res and res.data is not None:
            return {"claims": res.data}
        return {"claims": []}
    except Exception as e:
        log.error("payer_claims_list_failed", payer_id=payer_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch payer claims list.")

@router.get("/detail/{claim_id}")
async def get_claim_detail(claim_id: str):
    """Fetches a single claim detail payload for the Adjudication Screen"""
    supabase = get_supabase()
    try:
        res = getattr(supabase.table("claims").select("*, organizations(name), claim_audit_logs(*)").eq("id", claim_id).single(), "execute")()
        if res and res.data:
            return {"claim": res.data}
        raise HTTPException(status_code=404, detail="Claim not found")
    except HTTPException:
        raise
    except Exception as e:
        log.error("claim_detail_failed", claim_id=claim_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch claim detail")

@router.get("/payers")
async def list_payers():
    """
    Returns the list of enabled payers so the frontend can populate a dropdown
    when the medical coder wants to submit a claim.
    """
    supabase = get_supabase()
    try:
        res = getattr(supabase.table("payers").select("id, name, payer_type, base_allowed_multiplier").order("name"), "execute")()
        if res and res.data is not None:
            return {"payers": res.data}
        return {"payers": []}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch payers.")

@router.get("/payers/by-org/{org_id}")
async def get_payer_for_org(org_id: str):
    """
    Resolves the payer record for a given organization by name-matching.
    Example: Nathin is in 'Global Health Insurance' org -> matches the
    'Global Health Insurance' payer record so inbox shows only his claims.
    """
    supabase = get_supabase()
    try:
        org_res = getattr(
            supabase.table("organizations").select("name").eq("id", org_id).single(),
            "execute"
        )()
        if not org_res or not org_res.data:
            raise HTTPException(status_code=404, detail="Organization not found")
        org_name = org_res.data["name"]

        payer_res = getattr(
            supabase.table("payers")
            .select("id, name, payer_type, base_allowed_multiplier")
            .ilike("name", org_name)
            .limit(1),
            "execute"
        )()
        if payer_res and payer_res.data and len(payer_res.data) > 0:
            return {"payer": payer_res.data[0]}

        raise HTTPException(status_code=404, detail=f"No payer record found matching org '{org_name}'")
    except HTTPException:
        raise
    except Exception as e:
        log.error("payer_by_org_failed", org_id=org_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to resolve payer for organization.")

class AdjudicationRequest(BaseModel):
    action: str  # e.g., 'APPROVE', 'DENY'
    denial_reason: Optional[str] = None
    payer_responsibility_pct: float = 0.80  # Default 80% payer, 20% patient

@router.post("/adjudicate/{claim_id}")
async def adjudicate_claim(claim_id: str, req: AdjudicationRequest):
    """
    Simulates a Payer adjudicating (processing) a submitted claim.
    Calculates the 'Allowed Amount' based on the Payer's contract multiplier,
    determines what the Payer pays, and leaves the rest as Patient Responsibility.
    """
    supabase = get_supabase()
    
    log.info("claims_adjudicate_start", claim_id=claim_id, action=req.action)
    
    try:
        # 1. Fetch the claim and its associated payer details
        res = getattr(supabase.table("claims").select("*, payers(base_allowed_multiplier)").eq("id", claim_id).single(), "execute")()
        if not res or not res.data:
            raise HTTPException(status_code=404, detail="Claim not found")
            
        claim = res.data
        if claim["status"] in ["PAID", "DENIED", "PARTIALLY_PAID"]:
            raise HTTPException(status_code=400, detail=f"Claim is already {claim['status']}")
            
        # 2. Extract financial baseline
        billed_amount = float(claim.get("total_billed_amount", 0))
        
        if req.action == 'DENY':
            update_payload = {
                "status": "DENIED",
                "denial_reason": req.denial_reason or "Services not covered under patient plan.",
                "total_allowed_amount": 0,
                "total_paid_amount": 0,
                "patient_responsibility": billed_amount, # Patient owes the full billed amount if denied (simplified)
            }
        elif req.action == 'APPROVE':
            # 3. Calculate Allowed Amount (Contractual Adjustment)
            # To simulate RCM, we need the original base prices. 
            # We access them from the frozen claim_data snapshot.
            claim_data = claim.get("claim_data", {})
            financial_summary = claim_data.get("financial_summary", {})
            line_items = financial_summary.get("line_items", [])
            
            payer_multiplier = 1.0
            if claim.get("payers"):
                payer_multiplier = float(claim["payers"].get("base_allowed_multiplier", 1.0))
                
            # Allowed amount = (CMS Base Price) * (Payer Multiplier)
            total_allowed = 0.0
            for item in line_items:
                base = float(item.get("base_price", 0))
                total_allowed += base * payer_multiplier
                
            total_allowed = round(total_allowed, 2)
            
            # The payer cannot "allow" more than what the hospital billed.
            # If hospital billed $100 but allowed is $120, allowed caps at $100.
            total_allowed = min(total_allowed, billed_amount)
            
            # 4. Calculate Paid vs Patient Responsibility
            # Example: Allowed is $80. Payer pays 80% ($64). Patient owes 20% ($16).
            total_paid = round(total_allowed * req.payer_responsibility_pct, 2)
            patient_resp = round(total_allowed - total_paid, 2)
            
            update_payload = {
                "status": "PAID" if req.payer_responsibility_pct >= 1.0 else "PARTIALLY_PAID",
                "total_allowed_amount": total_allowed,
                "total_paid_amount": total_paid,
                "patient_responsibility": patient_resp,
                "denial_reason": None
            }
        else:
            raise HTTPException(status_code=400, detail="Invalid action. Use APPROVE or DENY.")
            
        # 5. Save the adjudication back to the database
        # We also need to set adjudicated_at, using raw sql string if possible, or omit for now
        update_res = getattr(supabase.table("claims").update(update_payload).eq("id", claim_id), "execute")()
        
        # === Insert HIPAA Audit Trail ===
        try:
            audit_log = {
                "claim_id": claim_id,
                "previous_status": claim["status"],
                "new_status": update_payload["status"],
                "action_notes": f"Manual Adjudication: {req.action}. " + (req.denial_reason if req.denial_reason is not None else "")
            }
            getattr(supabase.table("claim_audit_logs").insert(audit_log), "execute")()
        except Exception as audit_e:
            log.error("claims_adjudicate_audit_failed", error=str(audit_e))
        
        log.info("claims_adjudicate_success", claim_id=claim_id, payload=update_payload)
        return {
            "status": "success",
            "message": f"Claim {req.action.lower()}ed successfully.",
            "adjudication_details": update_payload
        }

    except HTTPException:
        raise
    except Exception as e:
        log.error("claims_adjudicate_failed", claim_id=claim_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

class AppealRequest(BaseModel):
    justification: str

@router.post("/appeal/{claim_id}")
async def appeal_claim(claim_id: str, req: AppealRequest):
    """
    Allows a Hospital Biller to appeal a Denied or Partially Paid claim by providing justification.
    """
    supabase = get_supabase()
    log.info("claims_appeal_start", claim_id=claim_id)

    try:
        # 1. Fetch the claim
        res = getattr(supabase.table("claims").select("*, payers(name)").eq("id", claim_id).single(), "execute")()
        if not res or not res.data:
            raise HTTPException(status_code=404, detail="Claim not found")

        claim = res.data
        if claim["status"] not in ["DENIED", "PARTIALLY_PAID"]:
            raise HTTPException(status_code=400, detail=f"Cannot appeal a claim in {claim['status']} status. Must be DENIED or PARTIALLY_PAID.")

        # 2. Extract original denial reason (if any)
        # Note: We keep the denial_reason in the db so the hospital knows what they are fighting.
        
        update_payload = {
            "status": "APPEALED",
            # We don't wipe out the denial_reason because the abstract concept of a denial remains part of the claim's history
        }

        # 3. Save the status back to the database
        update_res = getattr(supabase.table("claims").update(update_payload).eq("id", claim_id), "execute")()

        # 4. === Insert HIPAA Audit Trail ===
        try:
            audit_log = {
                "claim_id": claim_id,
                "previous_status": claim["status"],
                "new_status": "APPEALED",
                "action_notes": f"Hospital Appeal Filed: {req.justification}"
            }
            getattr(supabase.table("claim_audit_logs").insert(audit_log), "execute")()
        except Exception as audit_e:
            log.error("claims_appeal_audit_failed", error=str(audit_e))

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
        raise HTTPException(status_code=500, detail=str(e))


from fastapi.responses import PlainTextResponse

@router.get("/export/edi/{claim_id}", response_class=PlainTextResponse)
async def export_edi_837(claim_id: str):
    """
    Generates a simulated ANSI ASC X12 EDI 837 Health Care Claim format.
    Real-world clearinghouses accept these nasty text strings.
    """
    supabase = get_supabase()
    
    try:
        # Fetch highly detailed claim snapshot
        # organizations.address is not in all deployments — only select existing columns
        res = getattr(supabase.table("claims").select("*, organizations(name), payers(name, payer_type)").eq("id", claim_id).single(), "execute")()
        if not res or not res.data:
            raise HTTPException(status_code=404, detail="Claim not found")
        
        claim = res.data
        org_name = claim.get("organizations", {}).get("name", "INTEGRONIX HOSPITAL")
        payer_name = claim.get("payers", {}).get("name", "UNKNOWN PAYER")
        patient_name = claim.get("patient_name", "UNKNOWN")
        patient_dob = claim.get("patient_dob", "20000101")
        total_billed = claim.get("total_billed_amount", 0.00)
        
        # simulated parts
        sender_id = "INTGRNX01"
        receiver_id = payer_name.upper()[:9]
        
        # Build out a fake (but structurally accurate-looking) X12 string
        edi_lines = [
            f"ISA*00*          *00*          *ZZ*{sender_id:<15}*ZZ*{receiver_id:<15}*260315*1200*U*00501*000000001*0*T*:~",
            f"GS*HC*{sender_id}*{receiver_id}*20260315*1200*1*X*005010X222A1~",
            "ST*837*0001*005010X222A1~",
            f"BHT*0019*00*0123*20260315*1200*CH~",
            f"NM1*41*2*{org_name[:35].upper()}*****46*{sender_id}~",
            f"NM1*40*2*{payer_name[:35].upper()}*****46*{receiver_id}~",
            f"HL*1**20*1~", # hierarchical level (billing provider)
            f"PRV*BI*PXC*207Q00000X~", # billing provider specialty
            f"NM1*85*2*{org_name[:35].upper()}*****XX*1234567890~", # NPI
            f"HL*2*1*22*0~", # hierarchical level (subscriber)
            f"SBR*P**12345****11~", # subscriber info
            f"NM1*IL*1*{patient_name.upper().split()[-1]}*{patient_name.upper().split()[0]}****MI*ABC123456789~", # patient name
            f"DMG*D8*{patient_dob.replace('-', '')}*U~", # demographics
            f"CLM*{claim_id.split('-')[0]}*{total_billed:.2f}***11:B:1*Y*A*Y*I~", # claim info
            # Usually there would be an HI segment here with diagnosis (ICD-10) codes.
        ]
        
        # Now inject the line items (CPT codes)
        claim_data = claim.get("claim_data", {})
        financial_summary = claim_data.get("financial_summary", {})
        line_items = financial_summary.get("line_items", [])
        
        for idx, item in enumerate(line_items, 1):
            cpt = item.get("cpt_code", "XXXXX")
            base = float(item.get("base_price", 0))
            edi_lines.extend([
                f"LX*{idx}~",
                f"SV1*HC:{cpt}*{base:.2f}*UN*1***1~", # service line
                f"DTP*472*D8*20260315~" # date of service
            ])
            
        edi_lines.extend([
            f"SE*{len(edi_lines)}*0001~",
            "GE*1*1~",
            "IEA*1*000000001~"
        ])
        
        return "\n".join(edi_lines)
    
    except HTTPException:
        raise
    except Exception as e:
        log.error("claims_edi_failed", claim_id=claim_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

