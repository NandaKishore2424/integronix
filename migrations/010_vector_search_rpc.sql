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
