"""
routes/code.py — Full Pipeline Endpoints

  POST /code/run      → accepts JSON body (raw_text)
  POST /code/run-pdf  → accepts multipart/form-data (PDF file)

8-node LangGraph pipeline:
  Node 1: doc_processing    → raw_text (from text or PDF bytes)
  Node 2: clinical_extract  → structured_entities via Groq LLM
  Node 3: snomed_resolve    → SNOMED concept resolution
  Node 4: snomed_icd_map    → SNOMED→ICD direct mapping
  Node 5: icd_embedding     → embedding fallback (if no direct map)
  Node 6: icd_decision      → deterministic ICD selection + multi-code list
  Node 7: audit_comparison  → human vs AI comparison + DRG flag
  Node 8: risk_scoring      → risk label + DB writes
"""
import uuid
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional, List
from agents.graph import build_integronix_graph, CodingState
from models import CodeRequest, CodeResponse
from config import settings
from logger import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/code", tags=["ICD Coding Pipeline"])

MAX_PDF_SIZE = 20 * 1024 * 1024  # 20 MB

_graph = None


def _get_graph():
    global _graph
    if _graph is None:
        _graph = build_integronix_graph()
    return _graph



# ── FHIR builder ───────────────────────────────────────────────────────────────

def _build_fhir_condition(icd_codes: list, session_id: str) -> dict:
    """
    Build a minimal FHIR R4 Condition resource.
    Primary code goes into code.coding, secondary/additional into extension.
    """
    if not icd_codes:
        return {}

    primary = icd_codes[0]
    codings = [{
        "system":  "http://hl7.org/fhir/sid/icd-10-cm",
        "version": "2024",
        "code":    primary["code"],
        "display": primary.get("description", ""),
    }]

    # Add secondary/additional codes as additional codings
    for c in icd_codes[1:]:
        codings.append({
            "system":    "http://hl7.org/fhir/sid/icd-10-cm",
            "version":   "2024",
            "code":      c["code"],
            "display":   c.get("description", ""),
            "extension": [{
                "url":         "http://hl7.org/fhir/StructureDefinition/condition-dueTo",
                "valueString": c.get("role", "secondary"),
            }],
        })

    return {
        "resourceType":  "Condition",
        "id":            session_id,
        "clinicalStatus": {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                "code":   "active",
            }]
        },
        "verificationStatus": {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                "code":   "confirmed",
            }]
        },
        "code": {
            "coding": codings,
            "text":   primary.get("description", ""),
        },
        "subject": {
            "reference": f"Patient/{session_id}",
        },
        "meta": {
            "source": "integronix-ai-coding-engine",
        },
    }


# ── Endpoint ───────────────────────────────────────────────────────────────────

async def _run_pipeline(initial_state: CodingState, session_id: str) -> CodeResponse:
    """Shared pipeline runner used by both /run and /run-pdf endpoints."""
    try:
        graph  = _get_graph()
        result = await graph.ainvoke(
            initial_state,
            config={"recursion_limit": 25},
        )
    except Exception as e:
        log.error("pipeline_failed", session_id=session_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline failed: {str(e)}",
        )

    icd_codes = result.get("icd_codes") or []

    return CodeResponse(
        session_id=session_id,
        final_icd_code=result.get("final_icd_code", "UNKNOWN"),
        confidence_score=result.get("confidence_score", 0.0),
        mapping_path=result.get("mapping_path", "unknown"),
        resolved_snomed_code=result.get("resolved_snomed_code"),
        candidates=result.get("candidate_icd_codes", []),
        icd_codes=icd_codes,
        discrepancy_type=result.get("discrepancy_type"),
        discrepancy=result.get("discrepancy"),
        financial_delta=result.get("financial_delta"),
        drg_flag=result.get("drg_flag"),
        risk_score=result.get("risk_score", 0.0),
        risk_label=result.get("risk_label", "UNKNOWN"),
        extraction_metadata=result.get("extraction_metadata") or {},
        fhir_condition=_build_fhir_condition(icd_codes, session_id),
        error_at=result.get("error_at"),
        document_source=result.get("document_source", "text_input"),
        ocr_used=result.get("ocr_used", False),
    )


@router.post(
    "/run",
    response_model=CodeResponse,
    summary="Run full ICD coding pipeline on raw clinical text",
)
async def run_full_pipeline(body: CodeRequest):
    """
    Full 8-node LangGraph pipeline — accepts raw clinical text (JSON).
    """
    if not body.raw_text or len(body.raw_text.strip()) < 20:
        raise HTTPException(
            status_code=400,
            detail="raw_text must be at least 20 characters.",
        )

    session_id = body.session_id or str(uuid.uuid4())

    initial_state: CodingState = {
        "session_id":     session_id,
        "raw_text":       body.raw_text.strip(),
        "human_icd_code": body.human_icd_code,
        "pdf_bytes":      None,
        "icd_version":    settings.who_icd_default_version,  # "ICD-11" or "ICD-10" per org
    }

    log.info(
        "pipeline_started",
        session_id=session_id,
        source="text",
        text_length=len(body.raw_text),
        has_human_code=bool(body.human_icd_code),
    )

    return await _run_pipeline(initial_state, session_id)


@router.post(
    "/run-pdf",
    response_model=CodeResponse,
    summary="Run full ICD coding pipeline on an uploaded PDF (discharge summary, SOAP, etc.)",
)
async def run_pdf_pipeline(
    file: UploadFile = File(..., description="PDF file — discharge summary, H&P, or progress notes"),
    human_icd_code: Optional[str] = Form(None, description="Existing ICD-10 code for audit comparison"),
    session_id: Optional[str] = Form(None),
):
    """
    Full 8-node LangGraph pipeline — accepts a PDF file via multipart/form-data.

    The PDF is read as bytes and passed to Node 1 (doc_processing) which:
      - Tries pdfplumber first (digital PDFs)
      - Falls back to Tesseract OCR (scanned/image PDFs)
    The rest of the pipeline is identical to /run.
    """
    # ── Validate file type ────────────────────────────────────────────────────
    content_type = file.content_type or ""
    if "pdf" not in content_type and not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are accepted. Please upload a .pdf file.",
        )

    # ── Read bytes & enforce size limit ───────────────────────────────────────
    pdf_bytes = await file.read()
    if len(pdf_bytes) > MAX_PDF_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"PDF too large. Maximum allowed size is 20 MB (got {len(pdf_bytes) // 1024 // 1024} MB).",
        )
    if len(pdf_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded PDF file is empty.")

    session_id = session_id or str(uuid.uuid4())

    initial_state: CodingState = {
        "session_id":     session_id,
        "pdf_bytes":      pdf_bytes,
        "raw_text":       "",           # Node 1 will populate this from PDF
        "human_icd_code": human_icd_code.strip().upper() if human_icd_code else None,
        "icd_version":    settings.who_icd_default_version,  # "ICD-11" or "ICD-10"
    }

    log.info(
        "pipeline_started",
        session_id=session_id,
        source="pdf",
        filename=file.filename,
        size_bytes=len(pdf_bytes),
        has_human_code=bool(human_icd_code),
    )

    return await _run_pipeline(initial_state, session_id)
