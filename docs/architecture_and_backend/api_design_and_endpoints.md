# API Design and Endpoints

## Design Principles

- **Simplicity and Power**: The API is designed to be simple to use while exposing the full power of the underlying agentic pipeline. We've consolidated the entire workflow into two primary endpoints.
- **API-First**: The frontend is fully decoupled from the backend logic, interacting only through this well-defined API.
- **Pydantic Models for Validation**: All request and response bodies are strictly defined and validated using Pydantic models, ensuring data integrity from end to end.
- **Auto-generated OpenAPI Docs**: FastAPI automatically generates interactive OpenAPI (Swagger) documentation, available at the `/docs` endpoint for easy exploration and testing.

---

## Base URL

The base URL for all API endpoints is:
```
http://localhost:8000/api/v1
```

---

## Core Endpoints

The complex, multi-step process of document analysis, coding, and auditing has been unified into two primary, powerful endpoints. This simplifies integration and use, as the client does not need to manage the stateful workflow; the LangGraph pipeline handles it internally.

---

### `POST /code/run`

This is the primary endpoint for processing raw clinical text. It accepts a JSON payload containing the clinical notes and other optional parameters, and returns the complete analysis after running the full pipeline.

**Request Body (`CodeRequest` model):**
```json
{
  "raw_text": "Patient is a 65-year-old male with a history of type 2 diabetes, presenting with...",
  "human_icd_code": "E11.9",
  "session_id": "optional-session-id-to-resume",
  "org_id": "org-uuid-for-settings-lookup"
}
```
- `raw_text` (str, required): The unstructured clinical text to be analyzed.
- `human_icd_code` (str, optional): An existing ICD code provided by a human coder. If supplied, the pipeline will run an audit comparison.
- `session_id` (str, optional): A unique identifier for the session. If not provided, a new one is generated.
- `org_id` (str, optional): The ID of the organization, used to fetch specific settings like the target ICD version (10 vs. 11).

**Response Body (`CodeResponse` model):**
The endpoint returns a rich JSON object containing the entire state of the completed pipeline run.
```json
{
  "session_id": "a1b2c3d4-...",
  "final_icd_code": "E11.42",
  "confidence_score": 0.95,
  "mapping_path": "snomed_to_icd_map",
  "icd_codes": [
    {"code": "E11.42", "description": "Type 2 diabetes mellitus with diabetic polyneuropathy", "role": "primary"},
    {"code": "I10", "description": "Essential (primary) hypertension", "role": "comorbidity"}
  ],
  "cpt_codes": [
    {"code": "99214", "description": "Office or other outpatient visit for the evaluation and management of an established patient..."}
  ],
  "discrepancy": "AI code is more specific, capturing 'diabetic polyneuropathy' from the text.",
  "financial_delta": 125.50,
  "risk_label": "LOW",
  "fhir_condition": {
    "resourceType": "Condition",
    ...
  },
  "decision_trace": "Final code E11.42 selected due to highest specificity score (0.9) and direct mention of 'neuropathy'...",
  ...
}
```

---

### `POST /code/run-pdf`

This endpoint provides the same functionality as `/code/run` but accepts a PDF file directly via a `multipart/form-data` request. The backend handles the text extraction automatically.

**Request:** `multipart/form-data`
- `file`: The PDF file binary.
- `human_icd_code` (optional): The human-provided ICD code for audit.
- `session_id` (optional): A session identifier.
- `org_id` (optional): The organization ID.

**Response:**
The response is identical to the `/code/run` endpoint, returning a `CodeResponse` object with the full pipeline results.

**Internal Action:**
The backend's `doc_processing` node intelligently extracts text from the PDF. It first attempts to read digital text using `pdfplumber`. If that fails or yields poor results (indicating a scanned document), it automatically falls back to using Tesseract OCR to extract text from the image-based PDF.

---

### `GET /health`

A standard health check endpoint to monitor the status of the API and its dependencies.

**Response:**
```json
{
  "status": "ok",
  "database": "connected",
  "llm_service": "reachable"
}
```

---

## Key Pydantic Models

These models define the data structures for requests and responses, ensuring type safety and clear contracts.

```python
# models.py

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from uuid import UUID

class CodeRequest(BaseModel):
    """Request to the /code/run endpoint."""
    raw_text: str = Field(..., min_length=20)
    human_icd_code: Optional[str] = None
    session_id: Optional[str] = None
    org_id: Optional[str] = None

class CodeResponse(BaseModel):
    """Unified response for the entire coding pipeline."""
    session_id: str
    final_icd_code: str
    confidence_score: float
    mapping_path: str
    icd_codes: List[Dict[str, Any]] = []
    cpt_codes: List[Dict[str, Any]] = []
    discrepancy: Optional[str] = None
    financial_delta: Optional[float] = None
    risk_label: Optional[str] = None
    fhir_condition: Optional[Dict[str, Any]] = None
    decision_trace: Optional[str] = None
    # ... other fields for detailed analysis
```

---

## Error Handling

The API uses standard HTTP status codes to indicate the outcome of a request.

| Status Code | Reason |
|---|---|
| `400 Bad Request` | Invalid or missing data in the request (e.g., `raw_text` is too short). |
| `404 Not Found` | The requested resource (e.g., an `org_id`) does not exist. |
| `413 Payload Too Large` | The uploaded PDF in `/code/run-pdf` exceeds the size limit (e.g., 20MB). |
| `422 Unprocessable Entity` | The request body fails Pydantic validation. |
| `500 Internal Server Error` | An unexpected error occurred within the pipeline (e.g., an external service like the LLM is down, or a database error occurred). |

All error responses include a `detail` key with a human-readable message.
```json
{
  "detail": "Pipeline failed: Error communicating with the LLM service."
}
```

