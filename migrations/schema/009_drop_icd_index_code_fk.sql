-- 009_drop_icd_index_code_fk.sql
-- Drop FK on icd_index_terms.code to allow partial index codes (e.g., I63.-)

ALTER TABLE IF EXISTS icd_index_terms
  DROP CONSTRAINT IF EXISTS icd_index_terms_code_fkey;
