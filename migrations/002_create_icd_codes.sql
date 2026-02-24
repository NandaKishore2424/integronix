-- ============================================================
-- Migration 002: ICD-10 Master Code Table
-- Primary reference table for all billable codes
-- ============================================================

CREATE TABLE icd_codes (
    code                TEXT        PRIMARY KEY,            -- e.g. "E11.22"
    description         TEXT        NOT NULL,              -- Full clinical description
    chapter             TEXT,                              -- e.g. "Endocrine, Nutritional, Metabolic"
    category            TEXT,                              -- Sub-category grouping
    is_billable         BOOLEAN     DEFAULT TRUE,          -- Only billable codes are accepted
    is_cc               BOOLEAN     DEFAULT FALSE,         -- Complication/Comorbidity flag
    is_mcc              BOOLEAN     DEFAULT FALSE,         -- Major CC flag (higher reimbursement)
    version             TEXT        DEFAULT 'ICD-10-CM-2024',
    system              TEXT        DEFAULT 'ICD-10-CM',   -- FHIR code system identifier
    base_reimbursement  NUMERIC     DEFAULT 0,             -- Simulated DRG base reimbursement ($)
    embedding           VECTOR(384),                       -- Semantic embedding for similarity search
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
