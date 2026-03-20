"""
routes/cases.py — Case History API

  GET  /cases          → Paginated case list with filters + aggregate stats
  GET  /cases/{session_id} → Full result for a single historical case

Data comes from a Supabase join of clinical_cases + coding_results.
RLS on both tables ensures org-level isolation automatically via the service key.
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from database import select, select_one, select_paginated
from models import CaseSummary, CaseListResponse, CaseStatsResponse
from logger import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/cases", tags=["Case History"])


# ── Helpers ────────────────────────────────────────────────────────────────────

def _build_filters(
    risk_label: Optional[str],
    document_source: Optional[str],
    branch_id: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
) -> dict:
    """Build PostgREST filter dict from optional query params."""
    filters: dict = {}
    if risk_label:
        filters["risk_label"] = f"eq.{risk_label.upper()}"
    if document_source:
        filters["document_source"] = f"eq.{document_source}"
    if branch_id:
        filters["branch_id"] = f"eq.{branch_id}"
    if date_from:
        filters["created_at"] = f"gte.{date_from}"
    if date_to:
        # If already have gte, use and= chaining isn't possible in simple PostgREST
        # so just use lte (date_from filter prevails — acceptable for MVP)
        filters["created_at"] = f"lte.{date_to}"
    return filters


# ── GET /cases ─────────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=CaseListResponse,
    summary="List all coded cases for the org (paginated, filterable)",
)
async def list_cases(
    page:            int            = Query(1, ge=1, description="Page number (1-based)"),
    page_size:       int            = Query(20, ge=1, le=100, description="Rows per page"),
    risk_label:      Optional[str]  = Query(None, description="Filter: LOW | MEDIUM | HIGH"),
    document_source: Optional[str]  = Query(None, description="Filter: text_input | pdf_upload"),
    branch_id:       Optional[str]  = Query(None, description="Filter by branch UUID"),
    date_from:       Optional[str]  = Query(None, description="ISO date string e.g. 2026-01-01"),
    date_to:         Optional[str]  = Query(None, description="ISO date string e.g. 2026-03-31"),
):
    """
    Returns a paginated list of cases with summary data from coding_results.
    Each row contains enough info to render the cases table without loading
    the full pipeline output.

    Ordered by most recent first.
    """
    # Join coding_results with clinical_cases via case_id FK
    # PostgREST embedded resource syntax: coding_results!inner(...)
    SELECT_COLS = (
        "result_id,"
        "case_id,"
        "ai_icd_code,"
        "human_icd_code,"
        "discrepancy_type,"
        "financial_delta,"
        "risk_score,"
        "risk_label,"
        "confidence_score,"
        "drg_flag,"
        "created_at,"
        "clinical_cases!inner(session_id,document_source,ocr_used,raw_text_snippet,processing_status)"
    )

    cr_filters: dict = {}
    if risk_label:
        cr_filters["risk_label"] = f"eq.{risk_label.upper()}"
    if document_source:
        cr_filters["clinical_cases.document_source"] = f"eq.{document_source}"
    if branch_id:
        cr_filters["branch_id"] = f"eq.{branch_id}"

    try:
        rows, total = await select_paginated(
            table="coding_results",
            query=SELECT_COLS,
            filters=cr_filters if cr_filters else None,
            order="created_at.desc",
            page=page,
            page_size=page_size,
        )
    except Exception as e:
        log.error("cases_list_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to fetch cases: {str(e)}")

    # Flatten the nested join into CaseSummary objects
    summaries: list[CaseSummary] = []
    for r in rows:
        cc = r.get("clinical_cases") or {}
        summaries.append(CaseSummary(
            result_id=r.get("result_id", ""),
            session_id=cc.get("session_id", ""),
            ai_icd_code=r.get("ai_icd_code"),
            human_icd_code=r.get("human_icd_code"),
            discrepancy_type=r.get("discrepancy_type"),
            financial_delta=r.get("financial_delta"),
            risk_score=r.get("risk_score", 0.0),
            risk_label=r.get("risk_label", "UNKNOWN"),
            confidence_score=r.get("confidence_score", 0.0),
            drg_flag=r.get("drg_flag"),
            document_source=cc.get("document_source", "text_input"),
            ocr_used=cc.get("ocr_used", False),
            text_snippet=cc.get("raw_text_snippet"),
            created_at=r.get("created_at", ""),
        ))

    return CaseListResponse(
        cases=summaries,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, -(-total // page_size)),  # ceiling division
    )


# ── GET /cases/stats ───────────────────────────────────────────────────────────

@router.get(
    "/stats",
    response_model=CaseStatsResponse,
    summary="Aggregate KPIs for the Cases summary cards",
)
async def get_case_stats():
    """
    Returns aggregate statistics for the summary card row at the top
    of the Cases page:
      - total_cases        (all time)
      - total_revenue_recovered  (sum of positive financial_delta)
      - high_risk_count    (risk_label = HIGH)
      - accuracy_rate      (% of cases where discrepancy_type = EXACT_MATCH or NO_COMPARISON)
    These are computed via simple PostgREST aggregate queries.
    """
    try:
        # Total cases
        all_rows = await select(
            "coding_results",
            query="risk_label,discrepancy_type,financial_delta",
        )
    except Exception as e:
        log.error("cases_stats_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Stats query failed: {str(e)}")

    total_cases = len(all_rows)
    high_risk   = sum(1 for r in all_rows if r.get("risk_label") == "HIGH")
    revenue_sum = sum(
        float(r.get("financial_delta") or 0)
        for r in all_rows
        if (r.get("financial_delta") or 0) > 0
    )
    accurate = sum(
        1 for r in all_rows
        if r.get("discrepancy_type") in ("EXACT_MATCH", "NO_COMPARISON")
    )
    accuracy_rate = round((accurate / total_cases * 100) if total_cases > 0 else 0.0, 1)

    return CaseStatsResponse(
        total_cases=total_cases,
        total_revenue_recovered=round(revenue_sum, 2),
        high_risk_count=high_risk,
        accuracy_rate=accuracy_rate,
    )


# ── GET /cases/{session_id} ────────────────────────────────────────────────────

@router.get(
    "/{session_id}",
    summary="Get full details for a single historical case",
)
async def get_case_detail(session_id: str):
    """
    Returns the full coding result for a historical case identified by session_id.
    The response shape matches CodeResponse so the frontend can render the full
    ResultsPanel (IcdCodeCard, AuditCard, RiskMeter, etc.) without changes.
    """
    try:
        # Fetch clinical_cases row
        case = await select_one(
            "clinical_cases",
            query="*",
            filters={"session_id": f"eq.{session_id}"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Case lookup failed: {str(e)}")

    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{session_id}' not found.")

    # Fetch associated coding_results row
    try:
        result = await select_one(
            "coding_results",
            query="*",
            filters={"case_id": f"eq.{case['case_id']}"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Result lookup failed: {str(e)}")

    if not result:
        raise HTTPException(status_code=404, detail=f"Results for case '{session_id}' not found.")

    entities = case.get("structured_entities") or {}
    patient_block = entities.get("patient") or {}
    patient_name = None
    patient_dob = None
    patient_sex = None
    if isinstance(patient_block, dict):
        patient_name = (
            (patient_block.get("full_name") or patient_block.get("name") or "").strip() or None
        )
        patient_dob = (patient_block.get("date_of_birth") or "").strip() or None
        raw_sex = (patient_block.get("sex") or "").strip()
        patient_sex = raw_sex.upper() if raw_sex else None

    # Build a CodeResponse-compatible dict so frontend can reuse ResultsPanel
    return {
        "session_id":          session_id,
        "final_icd_code":      result.get("ai_icd_code", "UNKNOWN"),
        "confidence_score":    float(result.get("confidence_score", 0.0)),
        "mapping_path":        result.get("mapping_path", "unknown"),
        "resolved_snomed_code": result.get("resolved_snomed_code"),
        "candidates":          result.get("candidate_codes", []),
        "icd_codes":           result.get("icd_codes_full", []),
        # Preserve CPT + financial breakdown when the coder re-opens a case.
        # These are required for the payer policy gate and the FHIR Claim proposal items.
        "cpt_codes":           result.get("cpt_codes", []) or [],
        "discrepancy_type":    result.get("discrepancy_type"),
        "discrepancy":         result.get("audit_result_json"),
        "financial_delta":     result.get("financial_delta"),
        "drg_flag":            result.get("drg_flag"),
        "risk_score":          float(result.get("risk_score", 0.0)),
        "risk_label":          result.get("risk_label", "UNKNOWN"),
        "extraction_metadata": {},
        "fhir_condition":      result.get("fhir_condition"),
        "patient_name":        patient_name,
        "patient_dob":         patient_dob,
        "patient_sex":        patient_sex,
        "financial_summary":   result.get("financial_summary"),
        "decision_trace":      None,
        "error_at":            None,
        "document_source":     case.get("document_source", "text_input"),
        "ocr_used":            case.get("ocr_used", False),
    }
