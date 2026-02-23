from pydantic import BaseModel
from typing import Optional, List


# ── Clinical Extraction Schemas ──────────────────────────────────────────────

class SnomedCandidate(BaseModel):
    code: Optional[str] = None
    description: str


class DiagnosisEntity(BaseModel):
    text: str
    severity: Optional[str] = None
    laterality: Optional[str] = None
    snomed_candidate: SnomedCandidate
    comorbidities: List[str] = []
    evidence_text: str


class ObservationEntity(BaseModel):
    loinc_description: str
    value: str
    unit: Optional[str] = None


class ExtractionResult(BaseModel):
    diagnoses: List[DiagnosisEntity]
    observations: List[ObservationEntity] = []


# ── ICD Code Schemas ─────────────────────────────────────────────────────────

class ICDCode(BaseModel):
    code: str
    description: str
    chapter: Optional[str] = None
    category: Optional[str] = None
    is_billable: bool
    is_cc: bool
    is_mcc: bool
    base_reimbursement: float


class ICDCandidate(ICDCode):
    similarity_score: float
    mapping_type: Optional[str] = None
    source: str  # "snomed_map" | "embedding"


# ── Coding Result Schemas ────────────────────────────────────────────────────

class AuditResult(BaseModel):
    type: str  # EXACT_MATCH | SPECIFICITY_IMPROVEMENT | UNSUPPORTED_CODE | OVERCODING
    ai_code: str
    human_code: str
    explanation: str
    evidence_text: str
    revenue_delta: float


class CodingResult(BaseModel):
    session_id: str
    final_icd_code: str
    confidence_score: float
    structured_entities: ExtractionResult
    candidate_codes: List[ICDCandidate]
    audit: Optional[AuditResult] = None
    risk_score: float
    risk_label: str  # LOW | MEDIUM | HIGH


# ── Request Schemas ───────────────────────────────────────────────────────────

class AuditRequest(BaseModel):
    session_id: str
    human_icd_code: str
