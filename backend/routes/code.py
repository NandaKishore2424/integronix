"""
routes/code.py — Full Pipeline Endpoint: POST /code

Accepts raw text (+ optional human ICD for audit) and runs the complete
7-node LangGraph pipeline:

  Node 1: doc_processing    → raw_text (already done if text provided)
  Node 2: clinical_extract  → structured_entities via Groq LLM
  Node 3: snomed_resolve    → SNOMED concept resolution
  Node 4: snomed_icd_map    → SNOMED→ICD direct mapping
  Node 6: icd_decision      → deterministic ICD selection (7-step algorithm)
  Node 7: audit_comparison  → human vs AI comparison (if human code provided)
  Node 8: risk_scoring      → risk label + DB writes

Returns the complete CodingResult with final ICD, confidence, audit, risk.
"""
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from agents.graph import build_integronix_graph, CodingState
from logger import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/code", tags=["ICD Coding Pipeline"])

# Compile graph once at module load (not per request)
_graph = None


def _get_graph():
    global _graph
    if _graph is None:
        _graph = build_integronix_graph()
    return _graph


# ── Request / Response models ──────────────────────────────────────────────────

class CodeRequest(BaseModel):
    raw_text: str
    session_id: Optional[str] = None
    human_icd_code: Optional[str] = None   # For audit comparison (Node 7)


class CodeResponse(BaseModel):
    session_id:         str
    final_icd_code:     str
    confidence_score:   float
    mapping_path:       str
    resolved_snomed_code: Optional[str]
    candidates:         list
    discrepancy_type:   Optional[str]
    discrepancy:        Optional[dict]
    financial_delta:    Optional[float]
    risk_score:         float
    risk_label:         str
    extraction_metadata: dict
    error_at:           Optional[str] = None


# ── Endpoint ───────────────────────────────────────────────────────────────────

@router.post(
    "/run",
    response_model=CodeResponse,
    summary="Run full ICD coding pipeline on raw clinical text",
)
async def run_full_pipeline(body: CodeRequest):
    """
    Full 7-node LangGraph pipeline.
    Provide raw_text (clinical notes). Optionally provide human_icd_code for audit.

    Pipeline: Extract → SNOMED → Direct Map → Deterministic ICD → Audit → Risk
    """
    if not body.raw_text or len(body.raw_text.strip()) < 20:
        raise HTTPException(
            status_code=400,
            detail="raw_text must be at least 20 characters.",
        )

    session_id = body.session_id or str(uuid.uuid4())

    # Build initial state — Node 1 (doc_processing) skipped since text provided
    initial_state: CodingState = {
        "session_id":      session_id,
        "raw_text":        body.raw_text.strip(),
        "human_icd_code":  body.human_icd_code,
        "pdf_bytes":       None,
    }

    log.info(
        "pipeline_started",
        session_id=session_id,
        text_length=len(body.raw_text),
        has_human_code=bool(body.human_icd_code),
    )

    try:
        graph  = _get_graph()
        # Start from clinical_extract since raw_text is already provided
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

    return CodeResponse(
        session_id=session_id,
        final_icd_code=result.get("final_icd_code", "UNKNOWN"),
        confidence_score=result.get("confidence_score", 0.0),
        mapping_path=result.get("mapping_path", "unknown"),
        resolved_snomed_code=result.get("resolved_snomed_code"),
        candidates=result.get("candidate_icd_codes", []),
        discrepancy_type=result.get("discrepancy_type"),
        discrepancy=result.get("discrepancy"),
        financial_delta=result.get("financial_delta"),
        risk_score=result.get("risk_score", 0.0),
        risk_label=result.get("risk_label", "UNKNOWN"),
        extraction_metadata=result.get("extraction_metadata") or {},
        error_at=result.get("error_at"),
    )
