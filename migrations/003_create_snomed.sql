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
