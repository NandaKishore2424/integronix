from pydantic import BaseModel, field_validator, model_validator
from pydantic import ConfigDict
from typing import Optional, List


# ── Clinical Extraction Schemas ──────────────────────────────────────────────

class SnomedCandidate(BaseModel):
    code: Optional[str] = None
    description: str

    @field_validator("code", mode="before")
    @classmethod
    def sanitize_null_string(cls, v):
        """LLM sometimes returns the string 'null' instead of JSON null. Fix it."""
        if isinstance(v, str) and v.strip().lower() in ("null", "none", ""):
            return None
        return v


class DiagnosisEntity(BaseModel):
    text: str
    severity: Optional[str] = None
    laterality: Optional[str] = None
    snomed_candidate: SnomedCandidate
    comorbidities: List[str] = []
    evidence_text: str

    @field_validator("severity", "laterality", mode="before")
    @classmethod
    def sanitize_null_fields(cls, v):
        """Convert string 'null' to actual None for optional fields."""
        if isinstance(v, str) and v.strip().lower() in ("null", "none", ""):
            return None
        return v


class ObservationEntity(BaseModel):
    loinc_description: str
    value: str
    unit: Optional[str] = None


class ExtractionResult(BaseModel):
    diagnoses: List[DiagnosisEntity]
    observations: List[ObservationEntity] = []


# ── ICD Code Schemas ──────────────────────────────────────────────────────────

class ICDCode(BaseModel):
    code: str
    description: str
    chapter: Optional[str] = None
    category: Optional[str] = None
    is_billable: bool
    is_cc: bool
    is_mcc: bool
    base_reimbursement: float
    icd_version: str = "ICD-10-CM-2024"     # Version tracking ✅


class ICDCandidate(ICDCode):
    similarity_score: float
    mapping_type: Optional[str] = None
    source: str   # "snomed_map" | "embedding" | "text_search"


# ── Audit & Result Schemas ────────────────────────────────────────────────────

class AuditResult(BaseModel):
    type: str   # EXACT_MATCH | SPECIFICITY_IMPROVEMENT | UNSUPPORTED_CODE | OVERCODING
    ai_code: str
    human_code: str
    explanation: str
    evidence_text: str
    revenue_delta: float


class ExtractionMetadata(BaseModel):
    """Version tracking for every LLM call — logged to audit_log table."""
    model_config = ConfigDict(protected_namespaces=())

    model: str
    llm_version: str        # renamed from model_version to avoid Pydantic namespace conflict
    icd_version: str
    snomed_version: str
    attempt: int = 1



class CodingResult(BaseModel):
    session_id: str
    final_icd_code: str
    confidence_score: float
    structured_entities: ExtractionResult
    extraction_metadata: Optional[ExtractionMetadata] = None   # Version tracking ✅
    candidate_codes: List[ICDCandidate]
    audit: Optional[AuditResult] = None
    risk_score: float
    risk_label: str   # LOW | MEDIUM | HIGH
    # Error tracking
    error_at: Optional[str] = None
    error_detail: Optional[str] = None


# ── Request / Response Schemas ─────────────────────────────────────────────────

class AuditRequest(BaseModel):
    session_id: str
    human_icd_code: str


class CodeRequest(BaseModel):
    """Request body for POST /api/v1/code/run"""
    raw_text: str
    session_id: Optional[str] = None
    human_icd_code: Optional[str] = None


class CodeResponse(BaseModel):
    """Response from POST /api/v1/code/run or /api/v1/code/run-pdf"""
    session_id:           str
    final_icd_code:       str
    confidence_score:     float
    mapping_path:         str
    resolved_snomed_code: Optional[str] = None
    candidates:           list = []
    icd_codes:            List[dict] = []
    discrepancy_type:     Optional[str] = None
    discrepancy:          Optional[dict] = None
    financial_delta:      Optional[float] = None
    drg_flag:             Optional[str] = None
    risk_score:           float
    risk_label:           str
    extraction_metadata:  dict = {}
    fhir_condition:       Optional[dict] = None
    error_at:             Optional[str] = None
    # Document source tracking (Phase 6A)
    document_source:      Optional[str] = None  # "text_input" | "pdf_upload"
    ocr_used:             Optional[bool] = None


# ── Phase 6B: Case History models ─────────────────────────────────────────────

class CaseSummary(BaseModel):
    """One row in the Case History table."""
    result_id:        str
    session_id:       str
    ai_icd_code:      Optional[str] = None
    human_icd_code:   Optional[str] = None
    discrepancy_type: Optional[str] = None
    financial_delta:  Optional[float] = None
    risk_score:       float
    risk_label:       str
    confidence_score: float
    drg_flag:         Optional[str] = None
    document_source:  Optional[str] = None
    ocr_used:         Optional[bool] = None
    text_snippet:     Optional[str] = None   # First 300 chars of clinical text
    created_at:       str


class CaseListResponse(BaseModel):
    """Paginated list of case summaries."""
    cases:       List[CaseSummary]
    total:       int
    page:        int
    page_size:   int
    total_pages: int


class CaseStatsResponse(BaseModel):
    """Aggregate KPIs for the Cases page header cards."""
    total_cases:              int
    total_revenue_recovered:  float
    high_risk_count:          int
    accuracy_rate:            float   # Percentage 0-100


# ── Phase 6C: Analytics Dashboard models ────────────────────────────────────

class TrendPoint(BaseModel):
    """One day in the 30-day trend series."""
    date:    str    # YYYY-MM-DD
    cases:   int
    revenue: float


class AnalyticsOverview(BaseModel):
    """Top-level analytics payload for the /analytics/overview endpoint."""
    total_cases:              int
    total_revenue_recovered:  float
    avg_confidence:           float   # 0-100
    high_risk_rate:           float   # 0-100
    risk_distribution:        dict    # {LOW: n, MEDIUM: n, HIGH: n}
    source_distribution:      dict    # {text_input: n, pdf_upload: n}
    trend:                    List[TrendPoint]


class TopCodeItem(BaseModel):
    """One row in the Top Codes table."""
    code:            str
    count:           int
    avg_revenue:     float
    avg_risk:        float
    top_discrepancy: str


class AnalyticsTopCodes(BaseModel):
    """Top 10 ICD codes by frequency."""
    codes: List[TopCodeItem]


class DiscrepancyBreakdown(BaseModel):
    """One slice of the discrepancy type donut chart."""
    type:  str
    label: str
    count: int
