"""
routes/parse.py — Document upload and clinical extraction endpoints.

POST /upload  → accepts PDF, returns session_id + raw extracted text
POST /parse   → accepts raw_text, returns structured ExtractionResult JSON
"""
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException, Body
from pydantic import BaseModel

from services.pdf_service import extract_text_from_pdf
from services.extraction_service import extract_clinical_entities
from models import ExtractionResult

router = APIRouter(prefix="/parse", tags=["Clinical Extraction"])


# ── Request / Response models ─────────────────────────────────────────────────

class UploadResponse(BaseModel):
    session_id: str
    raw_text: str
    char_count: int
    message: str


class ParseRequest(BaseModel):
    raw_text: str
    session_id: str | None = None


class ParseResponse(BaseModel):
    session_id: str
    extraction: ExtractionResult
    diagnosis_count: int
    observation_count: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/upload",
    response_model=UploadResponse,
    summary="Upload a clinical PDF and extract raw text",
)
async def upload_document(file: UploadFile = File(...)):
    """
    Step 1: Upload a PDF clinical document.
    Returns raw extracted text and a session_id for downstream processing.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported. Please upload a .pdf file.",
        )

    contents = await file.read()

    if len(contents) > 10 * 1024 * 1024:  # 10 MB limit
        raise HTTPException(
            status_code=413,
            detail="File too large. Maximum size is 10 MB.",
        )

    try:
        raw_text = extract_text_from_pdf(contents)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    session_id = str(uuid.uuid4())

    return UploadResponse(
        session_id=session_id,
        raw_text=raw_text,
        char_count=len(raw_text),
        message="Text extracted successfully. Use POST /parse to extract clinical entities.",
    )


@router.post(
    "/run",
    response_model=ParseResponse,
    summary="Extract structured clinical entities from raw text using Groq LLM",
)
async def parse_clinical_text(body: ParseRequest):
    """
    Step 2: Extract structured clinical entities from raw text.
    Calls Groq LLM with a strict prompt. Returns validated ExtractionResult.
    LLM extracts diagnoses + SNOMED candidates. Never generates ICD codes.
    """
    if not body.raw_text or len(body.raw_text.strip()) < 50:
        raise HTTPException(
            status_code=400,
            detail="raw_text is too short. Minimum 50 characters required.",
        )

    try:
        extraction = await extract_clinical_entities(body.raw_text)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"LLM extraction failed: {str(e)}",
        )

    session_id = body.session_id or str(uuid.uuid4())

    return ParseResponse(
        session_id=session_id,
        extraction=extraction,
        diagnosis_count=len(extraction.diagnoses),
        observation_count=len(extraction.observations),
    )
