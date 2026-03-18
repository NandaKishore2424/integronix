-- 008_icd_structure_and_indexing.sql
-- ICD structure + search layer expansion

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ==============================
-- Extend icd_codes
-- ==============================
ALTER TABLE IF EXISTS icd_codes
  ADD COLUMN IF NOT EXISTS code_raw TEXT;

COMMENT ON COLUMN icd_codes.code_raw IS 'Dotless ICD code (e.g., A000) for deterministic joins.';

-- ==============================
-- ICD hierarchy table
-- ==============================
CREATE TABLE IF NOT EXISTS icd_code_hierarchy (
  code TEXT PRIMARY KEY REFERENCES icd_codes(code) ON DELETE CASCADE,
  parent_code TEXT REFERENCES icd_codes(code),
  level INT NOT NULL,
  chapter TEXT,
  section TEXT,
  full_path TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS icd_code_hierarchy_parent_code_idx
  ON icd_code_hierarchy(parent_code);

CREATE INDEX IF NOT EXISTS icd_code_hierarchy_level_idx
  ON icd_code_hierarchy(level);

COMMENT ON TABLE icd_code_hierarchy IS 'ICD-10-CM hierarchy (parent-child tree) parsed from tabular XML.';
COMMENT ON COLUMN icd_code_hierarchy.code IS 'ICD code (dotted format) for this node.';
COMMENT ON COLUMN icd_code_hierarchy.parent_code IS 'Immediate parent ICD code (dotted); NULL for root nodes.';
COMMENT ON COLUMN icd_code_hierarchy.level IS 'Depth in ICD hierarchy (chapter/section/category/subcategory/code).';
COMMENT ON COLUMN icd_code_hierarchy.chapter IS 'Chapter description from tabular XML.';
COMMENT ON COLUMN icd_code_hierarchy.section IS 'Section description from tabular XML.';
COMMENT ON COLUMN icd_code_hierarchy.full_path IS 'Materialized path of codes or names for fast traversal.';

-- ==============================
-- ICD metadata table
-- ==============================
CREATE TABLE IF NOT EXISTS icd_code_metadata (
  code TEXT PRIMARY KEY REFERENCES icd_codes(code) ON DELETE CASCADE,
  inclusion_terms TEXT[],
  excludes1 TEXT[],
  excludes2 TEXT[],
  notes TEXT[],
  created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE icd_code_metadata IS 'ICD-10-CM metadata and coding rules (includes/excludes/notes).';
COMMENT ON COLUMN icd_code_metadata.inclusion_terms IS 'Inclusion terms for the code as defined in tabular XML.';
COMMENT ON COLUMN icd_code_metadata.excludes1 IS 'Excludes1 notes (mutually exclusive conditions).';
COMMENT ON COLUMN icd_code_metadata.excludes2 IS 'Excludes2 notes (not included here).';
COMMENT ON COLUMN icd_code_metadata.notes IS 'Additional notes (codeFirst/useAdditionalCode/codeAlso/sevenChr).';

-- ==============================
-- ICD index (search) table
-- ==============================
CREATE TABLE IF NOT EXISTS icd_index_terms (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  term TEXT NOT NULL,
  normalized_term TEXT NOT NULL,
  code TEXT REFERENCES icd_codes(code),
  parent_term TEXT,
  level INT,
  is_redirect BOOLEAN DEFAULT FALSE,
  redirect_to TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS icd_index_terms_normalized_term_idx
  ON icd_index_terms(normalized_term);

CREATE INDEX IF NOT EXISTS icd_index_terms_code_idx
  ON icd_index_terms(code);

COMMENT ON TABLE icd_index_terms IS 'ICD-10-CM index (semantic lookup terms) parsed from index XML.';
COMMENT ON COLUMN icd_index_terms.normalized_term IS 'Lowercased/normalized term string for search.';
COMMENT ON COLUMN icd_index_terms.parent_term IS 'Parent term in the index term tree.';
COMMENT ON COLUMN icd_index_terms.is_redirect IS 'True if term redirects via <see> to another term.';
COMMENT ON COLUMN icd_index_terms.redirect_to IS 'Target term for redirect entries.';
