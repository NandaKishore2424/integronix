# 16 — SQL Schema: SNOMED Support & Full Database

> **This is the complete, authoritative database schema for Integronix.**
> Run all SQL in Supabase → SQL Editor in the order shown here.

---

## Step 0: Enable Required Extensions

```sql
-- Run first, before any table creation
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

---

## Step 1: ICD Master Table (Updated)

```sql
CREATE TABLE icd_codes (
    code                TEXT        PRIMARY KEY,        -- e.g. "E11.22"
    description         TEXT        NOT NULL,           -- Full description
    chapter             TEXT,                           -- e.g. "Endocrine, Nutritional, Metabolic"
    category            TEXT,                           -- Sub-category
    is_billable         BOOLEAN     DEFAULT TRUE,
    is_cc               BOOLEAN     DEFAULT FALSE,      -- Complication/Comorbidity flag
    is_mcc              BOOLEAN     DEFAULT FALSE,      -- Major Complication/Comorbidity flag
    version             TEXT        DEFAULT 'ICD-10-CM-2024',
    system              TEXT        DEFAULT 'ICD-10-CM', -- Code system identifier for FHIR
    base_reimbursement  NUMERIC     DEFAULT 0,          -- Simulated DRG reimbursement
    embedding           VECTOR(384),                    -- Semantic embedding of description
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
```

---

## Step 2: SNOMED Concepts Table (NEW)

```sql
CREATE TABLE snomed_concepts (
    snomed_code     TEXT        PRIMARY KEY,    -- e.g. "44054006"
    description     TEXT        NOT NULL,       -- Fully Specified Name (FSN)
    synonyms        TEXT[],                     -- Common synonyms for matching
    semantic_tag    TEXT,                       -- e.g. "(disorder)", "(finding)", "(procedure)"
    hierarchy       TEXT,                       -- Clinical hierarchy: "Clinical finding" etc.
    is_active       BOOLEAN     DEFAULT TRUE,
    version         TEXT        DEFAULT 'SNOMED-CT-2024',
    embedding       VECTOR(384),                -- Semantic embedding for fallback similarity
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

---

## Step 3: SNOMED → ICD Crosswalk Table (NEW)

```sql
CREATE TABLE snomed_icd_map (
    id              SERIAL      PRIMARY KEY,
    snomed_code     TEXT        NOT NULL REFERENCES snomed_concepts(snomed_code),
    icd_code        TEXT        NOT NULL REFERENCES icd_codes(code),
    mapping_type    TEXT        NOT NULL
                    CHECK (mapping_type IN ('exact', 'narrower', 'broader', 'approximate')),
    confidence      NUMERIC     DEFAULT 1.0 CHECK (confidence BETWEEN 0.0 AND 1.0),
    is_primary      BOOLEAN     DEFAULT TRUE,  -- Is this the best/preferred mapping?
    notes           TEXT,                      -- Why this mapping exists
    source          TEXT        DEFAULT 'manual', -- 'manual' | 'umls' | 'snomed-official'
    UNIQUE (snomed_code, icd_code)
);
```

**Mapping type guide:**
| Type | When to Use | Trust Level |
|---|---|---|
| `exact` | Perfect semantic equivalence | Highest — use directly |
| `narrower` | ICD is more specific than SNOMED | High — valid if evidence supports |
| `broader` | ICD is less specific | Medium — needs specificity rule |
| `approximate` | Related but not equivalent | Low — must pass validation |

---

## Step 4: Clinical Cases Table

```sql
CREATE TABLE clinical_cases (
    case_id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID        UNIQUE DEFAULT gen_random_uuid(),
    file_name           TEXT,
    raw_text            TEXT,                           -- Extracted PDF text
    raw_text_hash       TEXT,                           -- SHA-256 (don't store raw PHI in prod)
    structured_entities JSONB,                          -- FHIR-aligned Condition array
    observations        JSONB,                          -- FHIR Observation array (LOINC labs)
    processing_status   TEXT        DEFAULT 'PENDING'
                        CHECK (processing_status IN ('PENDING','PROCESSING','COMPLETE','FAILED')),
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    completed_at        TIMESTAMPTZ
);
```

---

## Step 5: Coding Results Table

```sql
CREATE TABLE coding_results (
    result_id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id             UUID        REFERENCES clinical_cases(case_id) ON DELETE CASCADE,
    --
    resolved_snomed_code TEXT       REFERENCES snomed_concepts(snomed_code),
    mapping_path        TEXT,       -- 'direct' | 'embedding_fallback' | 'rule_based'
    --
    ai_icd_code         TEXT        REFERENCES icd_codes(code),
    confidence_score    NUMERIC,    -- 0.0 to 1.0
    candidate_codes     JSONB,      -- Top 5 candidates with scores
    --
    human_icd_code      TEXT,       -- Human entered code (may not be in DB if invalid)
    discrepancy_type    TEXT
                        CHECK (discrepancy_type IN (
                            'EXACT_MATCH',
                            'SPECIFICITY_IMPROVEMENT',
                            'UNSUPPORTED_CODE',
                            'OVERCODING',
                            'NO_COMPARISON'
                        )),
    evidence_text       TEXT,       -- Supporting text from clinical document
    financial_delta     NUMERIC     DEFAULT 0,
    risk_score          NUMERIC     DEFAULT 0,
    risk_label          TEXT        CHECK (risk_label IN ('LOW','MEDIUM','HIGH')),
    --
    claim_json          JSONB,      -- FHIR Claim resource
    audit_result_json   JSONB,      -- Audit result FHIR extension
    --
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
```

---

## Step 6: Revenue Lookup Table

```sql
CREATE TABLE revenue_lookup (
    id                  SERIAL      PRIMARY KEY,
    icd_code            TEXT        REFERENCES icd_codes(code),
    drg_group           TEXT,                           -- e.g. "DRG-637"
    base_reimbursement  NUMERIC,                        -- Base $ amount
    cc_adjustment       NUMERIC     DEFAULT 0,          -- Added if CC present
    mcc_adjustment      NUMERIC     DEFAULT 0,          -- Added if MCC present
    effective_year      TEXT        DEFAULT '2024',
    notes               TEXT
);
```

---

## Step 7: All Indexes

```sql
-- ICD embedding index (semantic search)
CREATE INDEX ON icd_codes
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 50);

-- SNOMED embedding index (fallback search)
CREATE INDEX ON snomed_concepts
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 20);

-- SNOMED-ICD mapping lookups
CREATE INDEX idx_snomed_icd_map_snomed ON snomed_icd_map (snomed_code);
CREATE INDEX idx_snomed_icd_map_icd    ON snomed_icd_map (icd_code);
CREATE INDEX idx_snomed_icd_map_type   ON snomed_icd_map (mapping_type);

-- Case lookups
CREATE INDEX idx_clinical_cases_status ON clinical_cases (processing_status);

-- Result lookups
CREATE INDEX idx_coding_results_case   ON coding_results (case_id);
CREATE INDEX idx_coding_results_ai     ON coding_results (ai_icd_code);
```

---

## Step 8: Seed Core ICD Test Data

Run this to verify the schema is working before building anything:

```sql
INSERT INTO icd_codes
    (code, description, chapter, category, is_billable, is_cc, is_mcc, base_reimbursement)
VALUES
    ('E11.9',  'Type 2 diabetes mellitus without complications',              'Endocrine', 'Diabetes',      true, false, false, 1200),
    ('E11.22', 'Type 2 diabetes mellitus with diabetic chronic kidney disease','Endocrine','Diabetes',      true, true,  false, 2100),
    ('E11.40', 'Type 2 diabetes mellitus with diabetic neuropathy, unspecified','Endocrine','Diabetes',     true, true,  false, 1900),
    ('N18.3',  'Chronic kidney disease, stage 3',                             'Genitourinary','CKD',        true, true,  false, 1500),
    ('N18.4',  'Chronic kidney disease, stage 4',                             'Genitourinary','CKD',        true, true,  false, 1750),
    ('I10',    'Essential (primary) hypertension',                            'Circulatory', 'HTN',         true, false, false, 900),
    ('J18.9',  'Pneumonia, unspecified organism',                             'Respiratory', 'Pneumonia',   true, false, false, 1800),
    ('J96.00', 'Acute respiratory failure, unspecified',                      'Respiratory', 'Respiratory failure', true, false, true, 3500),
    ('A41.9',  'Sepsis, unspecified organism',                               'Infectious',  'Sepsis',      true, false, true,  5000),
    ('I50.9',  'Heart failure, unspecified',                                  'Circulatory', 'Heart failure',true,false, false, 2400);
```

---

## Step 9: Seed SNOMED Test Data

```sql
INSERT INTO snomed_concepts
    (snomed_code, description, semantic_tag, hierarchy)
VALUES
    ('44054006',  'Diabetes mellitus type 2',              '(disorder)',  'Clinical finding'),
    ('709044004', 'Chronic kidney disease stage 3',        '(disorder)',  'Clinical finding'),
    ('73211009',  'Diabetes mellitus',                     '(disorder)',  'Clinical finding'),
    ('59621000',  'Essential hypertension',                '(disorder)',  'Clinical finding'),
    ('233604007', 'Pneumonia',                             '(disorder)',  'Clinical finding');
```

---

## Step 10: Seed SNOMED → ICD Mappings

```sql
INSERT INTO snomed_icd_map
    (snomed_code, icd_code, mapping_type, confidence, is_primary, source)
VALUES
    ('44054006',  'E11.9',  'broader',   0.85, false, 'manual'),
    ('44054006',  'E11.22', 'narrower',  0.91, true,  'manual'),
    ('44054006',  'E11.40', 'narrower',  0.82, false, 'manual'),
    ('709044004', 'N18.3',  'exact',     0.99, true,  'manual'),
    ('59621000',  'I10',    'exact',     0.99, true,  'manual'),
    ('233604007', 'J18.9',  'broader',   0.80, true,  'manual');
```

---

## Verification Queries

After inserting, run these to confirm everything is working:

```sql
-- Verify ICD codes
SELECT code, description, is_billable, is_cc, base_reimbursement FROM icd_codes;

-- Verify SNOMED concepts
SELECT snomed_code, description, semantic_tag FROM snomed_concepts;

-- Verify crosswalk (JOIN)
SELECT
    sc.description AS snomed_description,
    sim.mapping_type,
    sim.confidence,
    ic.code AS icd_code,
    ic.description AS icd_description
FROM snomed_icd_map sim
JOIN snomed_concepts sc ON sc.snomed_code = sim.snomed_code
JOIN icd_codes ic ON ic.code = sim.icd_code
ORDER BY sim.confidence DESC;
```

You should see 6 rows with full SNOMED + ICD details. If this works — **schema is correct.**
