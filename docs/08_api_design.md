# 08 — API Design

## Design Principles

- **API-first**: Frontend is fully decoupled from backend logic
- **Pydantic models** for all request/response schemas
- **Auto-generated OpenAPI docs** at `/docs` via FastAPI
- Endpoints map directly to LangGraph workflow steps

---

## Base URL

```
http://localhost:8000/api/v1
```

---

## Endpoints

---

### `POST /upload`

Upload a clinical PDF and initiate a processing session.

**Request:** `multipart/form-data`
```
file: <PDF binary>
```

**Response:**
```json
{
  "session_id": "3f8a7b2c-...",
  "status": "PROCESSING",
  "message": "Document uploaded successfully. Processing initiated."
}
```

**Internal action:**
- Stores file temporarily
- Creates session record in `sessions` table
- Triggers `doc_processing_node` via LangGraph

---

### `POST /parse`

Trigger clinical entity extraction on raw text (or re-trigger on existing session).

**Request:**
```json
{
  "session_id": "3f8a7b2c-..."
}
```

**Response:**
```json
{
  "session_id": "3f8a7b2c-...",
  "structured_entities": {
    "diagnosis": "Type 2 Diabetes with diabetic peripheral neuropathy",
    "severity": "moderate",
    "laterality": null,
    "comorbidities": ["hypertension", "CKD stage 3"],
    "evidence_text": "Patient presents with bilateral foot pain and numbness..."
  }
}
```

---

### `POST /map`

Run deterministic ICD mapping on extracted entities.

**Request:**
```json
{
  "session_id": "3f8a7b2c-..."
}
```

**Response:**
```json
{
  "session_id": "3f8a7b2c-...",
  "final_icd_code": "E11.22",
  "description": "Type 2 diabetes mellitus with diabetic chronic kidney disease, stage 3",
  "confidence_score": 0.91,
  "is_cc": true,
  "candidate_codes": [
    {"code": "E11.22", "similarity": 0.91},
    {"code": "E11.40", "similarity": 0.78},
    {"code": "E11.9",  "similarity": 0.62}
  ]
}
```

---

### `POST /audit`

Compare AI-suggested code against a human-coded input.

**Request:**
```json
{
  "session_id": "3f8a7b2c-...",
  "human_icd_code": "E11.9"
}
```

**Response:**
```json
{
  "session_id": "3f8a7b2c-...",
  "ai_code": "E11.22",
  "human_code": "E11.9",
  "discrepancy_type": "SPECIFICITY_IMPROVEMENT",
  "explanation": "AI identified CKD stage 3 comorbidity from clinical text",
  "evidence_text": "Labs show eGFR 45, consistent with CKD Stage 3",
  "financial_delta": 450.00,
  "risk_score": 0.5,
  "risk_label": "MEDIUM"
}
```

---

### `GET /result/{session_id}`

Retrieve full pipeline result for a completed session.

**Response:**
```json
{
  "session_id": "3f8a7b2c-...",
  "status": "COMPLETE",
  "structured_entities": { ... },
  "final_icd_code": "E11.22",
  "confidence_score": 0.91,
  "discrepancy": { ... },
  "financial_delta": 450.00,
  "risk_score": 0.5,
  "risk_label": "MEDIUM"
}
```

---

### `GET /health`

Health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "db": "connected",
  "groq": "reachable"
}
```

---

## Pydantic Models (Backend)

```python
from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID

class StructuredEntities(BaseModel):
    diagnosis: str
    severity: str
    laterality: Optional[str]
    comorbidities: List[str]
    evidence_text: str

class MappingResult(BaseModel):
    final_icd_code: str
    description: str
    confidence_score: float
    is_cc: bool
    candidate_codes: List[dict]

class AuditResult(BaseModel):
    ai_code: str
    human_code: str
    discrepancy_type: str  # EXACT_MATCH | SPECIFICITY_IMPROVEMENT | UNSUPPORTED_CODE | OVERCODING
    explanation: str
    evidence_text: str
    financial_delta: float
    risk_score: float
    risk_label: str  # LOW | MEDIUM | HIGH
```

---

## Error Handling

| Status Code | When |
|---|---|
| `400 Bad Request` | Invalid session ID or missing fields |
| `404 Not Found` | Session not found |
| `422 Unprocessable Entity` | Schema validation failure |
| `500 Internal Server Error` | LLM failure or DB error |

All errors return:
```json
{
  "error": "Error message here",
  "detail": "Additional context if available"
}
```

---

## FastAPI App Entry Point

```python
# main.py
from fastapi import FastAPI
from routers import upload, parse, map, audit, result

app = FastAPI(
    title="Integronix Revenue Integrity Engine",
    version="1.0.0",
    description="Agentic ICD-10 coding, audit, and revenue intelligence API"
)

app.include_router(upload.router, prefix="/api/v1")
app.include_router(parse.router, prefix="/api/v1")
app.include_router(map.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")
app.include_router(result.router, prefix="/api/v1")
```
