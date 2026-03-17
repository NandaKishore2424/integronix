-- ============================================================
-- Migration 004: Clinical Cases + Coding Results
-- Two tables — coding_results depends on clinical_cases (FK)
-- ============================================================

-- 4a: Clinical Cases (one row per uploaded document)
CREATE TABLE clinical_cases (
    case_id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID        UNIQUE DEFAULT gen_random_uuid(),
    file_name           TEXT,
    raw_text            TEXT,                   -- Extracted PDF text
    raw_text_hash       TEXT,                   -- SHA-256 fingerprint (PHI de-identification)
    structured_entities JSONB,                  -- FHIR-aligned Condition array
    observations        JSONB,                  -- FHIR Observation array (LOINC labs/vitals)
    processing_status   TEXT        DEFAULT 'PENDING'
                        CHECK (processing_status IN ('PENDING','PROCESSING','COMPLETE','FAILED')),
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    completed_at        TIMESTAMPTZ             -- Set when status = COMPLETE or FAILED
);

-- 4b: Coding Results (one row per coding + audit result)
CREATE TABLE coding_results (
    result_id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id             UUID        REFERENCES clinical_cases(case_id) ON DELETE CASCADE,

    -- SNOMED resolution
    resolved_snomed_code TEXT       REFERENCES snomed_concepts(snomed_code),
    mapping_path        TEXT,       -- 'direct' | 'embedding_fallback' | 'rule_based'

    -- AI-generated ICD code
    ai_icd_code         TEXT        REFERENCES icd_codes(code),
    confidence_score    NUMERIC,    -- 0.0 to 1.0
    candidate_codes     JSONB,      -- Top 5 candidates with scores and reasoning

    -- Human comparison (audit)
    human_icd_code      TEXT,       -- NOT a FK — human codes may be invalid
    discrepancy_type    TEXT
                        CHECK (discrepancy_type IN (
                            'EXACT_MATCH',          -- AI and human agree
                            'SPECIFICITY_IMPROVEMENT', -- AI found more specific code
                            'UNSUPPORTED_CODE',     -- Human code not supported by evidence
                            'OVERCODING',           -- Human code is overcoded
                            'NO_COMPARISON'         -- No human code provided
                        )),
    evidence_text       TEXT,       -- Quote from clinical document supporting AI code

    -- Revenue impact
    financial_delta     NUMERIC     DEFAULT 0,   -- AI reimbursement - Human reimbursement ($)
    risk_score          NUMERIC     DEFAULT 0,   -- 0.0 to 1.0

    -- Labels
    risk_label          TEXT        CHECK (risk_label IN ('LOW','MEDIUM','HIGH')),

    -- FHIR output
    claim_json          JSONB,      -- FHIR Claim resource (for interoperability demo)
    audit_result_json   JSONB,      -- Audit result as FHIR extension

    created_at          TIMESTAMPTZ DEFAULT NOW()
);
-- ============================================================
-- Migration 018: Case History — Add Missing Columns
-- Adds full multi-code output + DRG flag to coding_results
-- so the Case History page can display them without re-running
-- the pipeline.
-- ============================================================

-- ── coding_results additions ──────────────────────────────────────────────────
ALTER TABLE coding_results
    ADD COLUMN IF NOT EXISTS icd_codes_full   JSONB,   -- Full ranked code list (primary + secondary + additional)
    ADD COLUMN IF NOT EXISTS drg_flag         TEXT     -- 'MCC_MISSED' | 'CC_MISSED' | 'MCC_OVERCODED'
                             CHECK (drg_flag IN ('MCC_MISSED', 'CC_MISSED', 'MCC_OVERCODED')),
    ADD COLUMN IF NOT EXISTS fhir_condition   JSONB;   -- Cached FHIR R4 Condition resource

-- ── clinical_cases additions ──────────────────────────────────────────────────
-- document_source and ocr_used already exist from migration 014.
-- Add raw_text_snippet for case list preview (first 300 chars of the note).
ALTER TABLE clinical_cases
    ADD COLUMN IF NOT EXISTS raw_text_snippet TEXT;    -- Truncated preview for cases table UI

-- ── Indexes for common Case History query patterns ────────────────────────────

-- Cases sorted by creation time per org (main list view)
CREATE INDEX IF NOT EXISTS idx_clinical_cases_org_created
    ON clinical_cases(organization_id, created_at DESC);

-- Filter cases by risk label
CREATE INDEX IF NOT EXISTS idx_coding_results_risk_label
    ON coding_results(risk_label);

-- Filter cases by branch + risk (branch-level manager view)
CREATE INDEX IF NOT EXISTS idx_coding_results_branch_risk
    ON coding_results(organization_id, branch_id, risk_label);

-- Session lookup (used to load a single case report)
CREATE INDEX IF NOT EXISTS idx_clinical_cases_session_id
    ON clinical_cases(session_id);

-- ── Comments ──────────────────────────────────────────────────────────────────
COMMENT ON COLUMN coding_results.icd_codes_full
    IS 'Serialised list of all AI-selected codes (primary, secondary, additional) with rationale';

COMMENT ON COLUMN coding_results.drg_flag
    IS 'DRG weight gap flag — set when AI detects a missed or overcoded MCC/CC vs human code';

COMMENT ON COLUMN coding_results.fhir_condition
    IS 'Cached FHIR R4 Condition resource for the primary code — enables EHR interop without re-running pipeline';

COMMENT ON COLUMN clinical_cases.raw_text_snippet
    IS 'First 300 characters of the clinical text — used for preview in Case History table';
