-- 012_coding_results_ai_icd_fkey_drop.sql
-- Allow ICD-11 (WHO API) and other codes not present in the local ICD-10-CM table.
-- The icd_codes table is seeded with ~98k ICD-10 rows; orgs on ICD-11 must persist
-- arbitrary WHO codes in coding_results without a reference-row requirement.

ALTER TABLE IF EXISTS coding_results
  DROP CONSTRAINT IF EXISTS coding_results_ai_icd_code_fkey;
