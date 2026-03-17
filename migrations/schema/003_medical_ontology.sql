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
-- ============================================================
-- Migration 003: SNOMED Concepts + SNOMED→ICD Crosswalk
-- Two tables — must be created in this order (FK dependency)
-- ============================================================

-- 3a: SNOMED Concepts (clinical terminology store)
CREATE TABLE snomed_concepts (
    snomed_code     TEXT        PRIMARY KEY,        -- e.g. "44054006"
    description     TEXT        NOT NULL,           -- SNOMED Fully Specified Name (FSN)
    synonyms        TEXT[],                         -- Common synonyms for matching
    semantic_tag    TEXT,                           -- e.g. "(disorder)", "(finding)", "(procedure)"
    hierarchy       TEXT,                           -- e.g. "Clinical finding", "Procedure"
    is_active       BOOLEAN     DEFAULT TRUE,       -- False = retired concept
    version         TEXT        DEFAULT 'SNOMED-CT-2024',
    embedding       VECTOR(384),                    -- Semantic embedding for fallback similarity search
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 3b: SNOMED → ICD-10 Crosswalk (deterministic mapping backbone)
CREATE TABLE snomed_icd_map (
    id              SERIAL      PRIMARY KEY,
    snomed_code     TEXT        NOT NULL REFERENCES snomed_concepts(snomed_code),
    icd_code        TEXT        NOT NULL REFERENCES icd_codes(code),
    mapping_type    TEXT        NOT NULL
                    CHECK (mapping_type IN ('exact', 'narrower', 'broader', 'approximate')),
                    -- exact      → direct 1:1 semantic match — safe to use directly
                    -- narrower   → ICD is more specific than SNOMED — valid with evidence
                    -- broader    → ICD is less specific — needs specificity scoring
                    -- approximate → similar but not equivalent — must pass validation
    confidence      NUMERIC     DEFAULT 1.0 CHECK (confidence BETWEEN 0.0 AND 1.0),
    is_primary      BOOLEAN     DEFAULT TRUE,   -- Best/preferred mapping for this SNOMED code
    notes           TEXT,                       -- Rationale for this mapping
    source          TEXT        DEFAULT 'manual',  -- 'manual' | 'umls' | 'snomed-official'
    UNIQUE (snomed_code, icd_code)
);
-- Migration: 020_cpt_codes.sql
-- Description: Creates the table to hold real CMS/AMA procedural billing codes
-- and their associated base Medicare rates and semantic embeddings.

-- Enable pgvector if not already enabled
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS public.cpt_hcpcs_codes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(10) UNIQUE NOT NULL,      -- The actual 5-digit CPT or alphanumeric HCPCS code
    description TEXT NOT NULL,             -- The official CMS short description
    code_type VARCHAR(20) NOT NULL,        -- 'CPT' (Level I) or 'HCPCS' (Level II)
    base_price NUMERIC(10, 2) NOT NULL,    -- The national CMS benchmark rate (USD)
    embedding vector(384),                 -- SentenceTransformer all-MiniLM-L6-v2 vector for semantic search
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Index for exact code lookups (e.g. searching "93306")
CREATE INDEX IF NOT EXISTS idx_cpt_code ON public.cpt_hcpcs_codes (code);

-- HNSW index for lighting-fast nearest-neighbor vector (semantic) searches
CREATE INDEX IF NOT EXISTS cpt_embedding_idx ON public.cpt_hcpcs_codes USING hnsw (embedding vector_cosine_ops);

-- RLS: Only authenticated users/roles can read
ALTER TABLE public.cpt_hcpcs_codes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow public read access to cpt codes"
ON public.cpt_hcpcs_codes FOR SELECT
USING (true);

-- Insert a trigger to manage updated_at on modifier
CREATE OR REPLACE FUNCTION update_cpt_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = timezone('utc'::text, now());
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_cpt_hcpcs_codes_modtime
    BEFORE UPDATE ON public.cpt_hcpcs_codes
    FOR EACH ROW
    EXECUTE PROCEDURE update_cpt_updated_at_column();
