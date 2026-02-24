"""
exceptions.py — Integronix custom exception hierarchy.

Rules:
  - All Integronix exceptions inherit from IntegronixError
  - Each exception has a code (for API responses) and a message
  - Node exceptions carry session_id and node_name for tracing

Usage:
    raise ExtractionError("LLM returned malformed JSON", session_id=sid)
"""


class IntegronixError(Exception):
    """Base exception for all Integronix errors."""
    code: str = "INTEGRONIX_ERROR"

    def __init__(self, message: str, **context):
        super().__init__(message)
        self.message = message
        self.context = context  # e.g. session_id, node_name, etc.

    def to_dict(self) -> dict:
        return {
            "error_code": self.code,
            "message": self.message,
            **self.context,
        }


# ── Extraction Layer ────────────────────────────────────────────────────────

class ExtractionError(IntegronixError):
    """LLM extraction failed — bad JSON, validation error, timeout."""
    code = "EXTRACTION_ERROR"


class LLMTimeoutError(IntegronixError):
    """Groq LLM call exceeded timeout."""
    code = "LLM_TIMEOUT"


class LLMRateLimitError(IntegronixError):
    """Groq rate limit hit."""
    code = "LLM_RATE_LIMIT"


# ── Document Layer ──────────────────────────────────────────────────────────

class PDFExtractionError(IntegronixError):
    """PDF text extraction failed — corrupted file or image-only PDF."""
    code = "PDF_EXTRACTION_ERROR"


# ── Coding Layer ─────────────────────────────────────────────────────────────

class SNOMEDResolutionError(IntegronixError):
    """SNOMED concept could not be resolved from DB or embedding."""
    code = "SNOMED_RESOLUTION_ERROR"


class ICDMappingError(IntegronixError):
    """No valid ICD-10 code found after all fallback strategies."""
    code = "ICD_MAPPING_ERROR"


class ICDValidationError(IntegronixError):
    """Selected ICD code failed clinical consistency validation."""
    code = "ICD_VALIDATION_ERROR"


# ── Agent / Graph Layer ───────────────────────────────────────────────────────

class NodeExecutionError(IntegronixError):
    """A LangGraph node raised an unhandled exception."""
    code = "NODE_EXECUTION_ERROR"

    def __init__(self, message: str, node_name: str, session_id: str = "", **context):
        super().__init__(message, node_name=node_name, session_id=session_id, **context)
        self.node_name = node_name
        self.session_id = session_id


# ── Database Layer ─────────────────────────────────────────────────────────

class DatabaseError(IntegronixError):
    """Supabase REST API call failed."""
    code = "DATABASE_ERROR"
