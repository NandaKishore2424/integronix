"""
routes/code.py — Full Pipeline Endpoint: POST /code/run

8-node LangGraph pipeline:
  Node 1: doc_processing    → raw_text pass-through
  Node 2: clinical_extract  → structured_entities via Groq LLM
  Node 3: snomed_resolve    → SNOMED concept resolution
  Node 4: snomed_icd_map    → SNOMED→ICD direct mapping
  Node 5: icd_embedding     → embedding fallback (if no direct map)
  Node 6: icd_decision      → deterministic ICD selection + multi-code list
  Node 7: audit_comparison  → human vs AI comparison + DRG flag
  Node 8: risk_scoring      → risk label + DB writes

Phase 5A additions:
  - icd_codes: multi-code list (primary + secondary + additional)
  - drg_flag: MCC/CC gap signal
  - fhir_condition: FHIR R4 Condition resource (enterprise signal)
"""
import uuid
from fastapi import APIRouter, HTTPException
from typing import Optional, List
from agents.graph import build_integronix_graph, CodingState
from models import CodeRequest, CodeResponse
from logger import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/code", tags=["ICD Coding Pipeline"])

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

@router.post(
    "/run",
    response_model=CodeResponse,
    summary="Run full ICD coding pipeline on raw clinical text",
)
async def run_full_pipeline(body: CodeRequest):
    """
    Full 8-node LangGraph pipeline.

    Returns:
    - final_icd_code: primary AI-selected ICD-10 code
    - icd_codes: ranked list (primary, secondary, additional) with rationale
    - fhir_condition: FHIR R4 Condition resource
    - drg_flag: DRG weight gap signal (MCC_MISSED, CC_MISSED, etc.)
    - discrepancy: audit comparison vs human code
    - risk_label: LOW / MEDIUM / HIGH
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
    }

    log.info(
        "pipeline_started",
        session_id=session_id,
        text_length=len(body.raw_text),
        has_human_code=bool(body.human_icd_code),
    )

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
    )
