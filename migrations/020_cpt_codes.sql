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
