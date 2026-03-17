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
