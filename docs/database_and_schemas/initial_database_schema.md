# 07 — Database Schema

## Design Decisions

- Use a **mini curated ICD-10 dataset** (~300–500 codes) for POC
- Do NOT import the full 70,000+ code set
- Use **pgvector** extension for embedding-based similarity search
- Revenue values are **simulated** (hardcoded) for POC stage
- All audit sessions are **logged** for traceability

---

## Tables

### Table 1: `icd_codes` (Master ICD Dataset)

```sql
CREATE TABLE icd_codes (
    code          VARCHAR(10)  PRIMARY KEY,        -- e.g. "E11.22"
    description   TEXT         NOT NULL,           -- Full description
    category      VARCHAR(100),                    -- e.g. "Endocrine, Nutritional, Metabolic"
    is_billable   BOOLEAN      DEFAULT TRUE,       -- Only billable codes allowed
    is_cc         BOOLEAN      DEFAULT FALSE,      -- Complication/Comorbidity flag
    is_mcc        BOOLEAN      DEFAULT FALSE,      -- Major Complication/Comorbidity
    version       VARCHAR(10)  DEFAULT 'ICD-10-CM-2024',
    embedding     VECTOR(1536),                    -- pgvector: semantic embedding of description
    created_at    TIMESTAMPTZ  DEFAULT NOW()
);
```

**Index for vector search:**
```sql
CREATE INDEX ON icd_codes USING ivfflat (embedding vector_cosine_ops);
```

---

### Table 2: `audit_log` (Per Session Audit Trail)

```sql
CREATE TABLE audit_log (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID         NOT NULL,
    raw_text_hash   VARCHAR(64), -- SHA-256 of raw text (not storing full PHI in prod)
    extracted_json  JSONB,       -- structured_entities from Clinical Extraction Agent
    ai_icd_code     VARCHAR(10)  REFERENCES icd_codes(code),
    human_icd_code  VARCHAR(10), -- May not be in DB if invalid
    discrepancy_type VARCHAR(50), -- EXACT_MATCH | SPECIFICITY_IMPROVEMENT | UNSUPPORTED_CODE | OVERCODING
    evidence_text   TEXT,        -- Supporting text from clinical document
    financial_delta NUMERIC(10, 2),
    risk_score      NUMERIC(4, 3),
    risk_label      VARCHAR(10), -- LOW | MEDIUM | HIGH
    confidence_score NUMERIC(4, 3),
    created_at      TIMESTAMPTZ  DEFAULT NOW()
);
```

---

### Table 3: `revenue_lookup` (Simulated Reimbursement Values)

```sql
CREATE TABLE revenue_lookup (
    id              SERIAL       PRIMARY KEY,
    icd_code        VARCHAR(10)  REFERENCES icd_codes(code),
    drg_group       VARCHAR(20), -- Simulated DRG group (e.g. "DRG-637")
    base_reimbursement NUMERIC(10, 2), -- Simulated $ value
    cc_adjustment   NUMERIC(10, 2) DEFAULT 0, -- Additional if CC
    mcc_adjustment  NUMERIC(10, 2) DEFAULT 0, -- Additional if MCC
    notes           TEXT
);
```

**Revenue delta calculation:**
```
delta = revenue_lookup[ai_icd].base_reimbursement 
      - revenue_lookup[human_icd].base_reimbursement
```

---

### Table 4: `sessions` (Processing Session Tracker)

```sql
CREATE TABLE sessions (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    file_name       VARCHAR(255),
    status          VARCHAR(20)  DEFAULT 'PENDING', -- PENDING | PROCESSING | COMPLETE | FAILED
    created_at      TIMESTAMPTZ  DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);
```

---

## pgvector Setup

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;
```

**Similarity Search Query (used in ICD Candidate Retrieval Node):**
```sql
SELECT code, description, is_billable, is_cc, is_mcc,
       1 - (embedding <=> $1::vector) AS similarity_score
FROM icd_codes
WHERE is_billable = TRUE
ORDER BY embedding <=> $1::vector
LIMIT 5;
```
*`$1` = embedding of the extracted diagnosis string from the LLM*

---

## Curated ICD Code Categories (for mini dataset)

Prioritize codes relevant to common hospital cases:

| Category | ICD Chapter |
|---|---|
| Diabetes & endocrine | E10–E14 |
| Cardiovascular | I00–I99 |
| Respiratory | J00–J99 |
| Sepsis & infections | A00–B99 |
| Renal / kidney | N00–N99 |
| Neoplasms (cancer) | C00–D49 |
| Neurological | G00–G99 |
| Injuries | S00–T98 |

Aim for: **50–100 codes per category**, ~500 total.

---

## Migration Strategy

Use Alembic for schema versioning:
```bash
alembic init alembic
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

This ensures ICD database updates are version-controlled and reproducible.
