-- ============================================================
-- Migration 007: All Indexes
-- Run AFTER all tables are created and seed data is inserted.
-- Note: ivfflat indexes require at least some rows to build efficiently.
-- ============================================================

-- ── ICD Embedding Index (dense vector search) ─────────────────────────────
-- Used by: icd_embedding node (fallback similarity search)
CREATE INDEX ON icd_codes
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 50);

-- ── SNOMED Embedding Index (dense vector search) ──────────────────────────
-- Used by: snomed_resolve node (embedding fallback)
CREATE INDEX ON snomed_concepts
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 20);

-- ── SNOMED-ICD Mapping Indexes ─────────────────────────────────────────────
-- Used by: snomed_icd_map node (direct mapping lookup)
CREATE INDEX idx_snomed_icd_map_snomed ON snomed_icd_map (snomed_code);
CREATE INDEX idx_snomed_icd_map_icd    ON snomed_icd_map (icd_code);
CREATE INDEX idx_snomed_icd_map_type   ON snomed_icd_map (mapping_type);

-- ── Clinical Cases Index ───────────────────────────────────────────────────
CREATE INDEX idx_clinical_cases_status ON clinical_cases (processing_status);

-- ── Coding Results Indexes ─────────────────────────────────────────────────
CREATE INDEX idx_coding_results_case   ON coding_results (case_id);
CREATE INDEX idx_coding_results_ai     ON coding_results (ai_icd_code);

-- ── Audit Log Indexes ──────────────────────────────────────────────────────
-- Used for: session-level decision trail queries
CREATE INDEX idx_audit_log_session     ON audit_log (session_id);
CREATE INDEX idx_audit_log_node        ON audit_log (node_name);
CREATE INDEX idx_audit_log_created     ON audit_log (created_at DESC);
-- ============================================================
-- Migration 010: Vector Similarity Search RPC Function
-- Used by Node 5 (icd_embedding.py) for fallback ICD matching.
-- Requires: pgvector extension + icd_codes.embedding populated.
-- ============================================================

CREATE OR REPLACE FUNCTION match_icd_codes(
    query_embedding  VECTOR(384),
    similarity_threshold FLOAT    DEFAULT 0.70,
    match_count      INT          DEFAULT 5
)
RETURNS TABLE (
    code                TEXT,
    description         TEXT,
    is_billable         BOOLEAN,
    is_cc               BOOLEAN,
    is_mcc              BOOLEAN,
    base_reimbursement  NUMERIC,
    version             TEXT,
    chapter             TEXT,
    similarity          FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        i.code,
        i.description,
        i.is_billable,
        i.is_cc,
        i.is_mcc,
        i.base_reimbursement,
        i.version,
        i.chapter,
        (1 - (i.embedding <=> query_embedding))::FLOAT AS similarity
    FROM icd_codes i
    WHERE
        i.embedding IS NOT NULL
        AND i.is_billable = TRUE
        AND (1 - (i.embedding <=> query_embedding)) > similarity_threshold
    ORDER BY i.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Also create SNOMED concept similarity search
CREATE OR REPLACE FUNCTION match_snomed_concepts(
    query_embedding  VECTOR(384),
    similarity_threshold FLOAT    DEFAULT 0.70,
    match_count      INT          DEFAULT 3
)
RETURNS TABLE (
    snomed_code  TEXT,
    description  TEXT,
    semantic_tag TEXT,
    similarity   FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        s.snomed_code,
        s.description,
        s.semantic_tag,
        (1 - (s.embedding <=> query_embedding))::FLOAT AS similarity
    FROM snomed_concepts s
    WHERE
        s.embedding IS NOT NULL
        AND s.is_active = TRUE
        AND (1 - (s.embedding <=> query_embedding)) > similarity_threshold
    ORDER BY s.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
-- Migration: 021_match_cpt_codes.sql
-- Description: Creates a Postgres function (RPC) to perform nearest-neighbor
-- similarity search on the cpt_hcpcs_codes pgvector column.

CREATE OR REPLACE FUNCTION match_cpt_codes(
  query_embedding vector(384),
  match_threshold float,
  match_count int
)
RETURNS TABLE (
  code varchar,
  description text,
  code_type varchar,
  base_price numeric,
  similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    cpt_hcpcs_codes.code,
    cpt_hcpcs_codes.description,
    cpt_hcpcs_codes.code_type,
    cpt_hcpcs_codes.base_price,
    1 - (cpt_hcpcs_codes.embedding <=> query_embedding) AS similarity
  FROM cpt_hcpcs_codes
  WHERE 1 - (cpt_hcpcs_codes.embedding <=> query_embedding) > match_threshold
  ORDER BY cpt_hcpcs_codes.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;
-- Migration: 022_dynamic_pricing_multiplier.sql
-- Description: Adds the cpt_pricing_multiplier to the org_settings table
-- to enable hospital-specific revenue cycle management calculations.

-- Add the new column with a default of 1.0 (standard CMS base rate)
ALTER TABLE public.org_settings 
ADD COLUMN IF NOT EXISTS cpt_pricing_multiplier NUMERIC(5,2) DEFAULT 1.00 NOT NULL;

-- Add a check constraint to ensure the multiplier is valid (e.g., between 0.1 and 10.0)
ALTER TABLE public.org_settings
ADD CONSTRAINT check_cpt_multiplier_range 
CHECK (cpt_pricing_multiplier >= 0.1 AND cpt_pricing_multiplier <= 10.0);

-- Provide a comment for database documentation
COMMENT ON COLUMN public.org_settings.cpt_pricing_multiplier IS 'Multiplier applied to the base CMS CPT price to calculate this specific organizations gross charge.';

-- Update the "Premium Care Institute" to have a 1.8 multiplier
UPDATE public.org_settings
SET cpt_pricing_multiplier = 1.80
FROM public.organizations
WHERE org_settings.organization_id = organizations.id
  AND organizations.name ILIKE '%Premium%';

-- Update "City General Hospital" to a 1.2 multiplier
UPDATE public.org_settings
SET cpt_pricing_multiplier = 1.20
FROM public.organizations
WHERE org_settings.organization_id = organizations.id
  AND organizations.name ILIKE '%City%';
