# SNOMED-ICD Map Fix - 2026-03-19

## Summary
We standardized the SNOMED-to-ICD bridge table naming and reseeded a small, high-value demo mapping set so the deterministic mapping path works cleanly in Supabase.

## What Changed
- Renamed the bridge column to `icd_code_id` (from `icd_code`) if it existed.
- Ensured `icd_codes.code` has a unique constraint for FK integrity.
- Recreated the FK from `snomed_icd_map.icd_code_id` to `icd_codes.code` with cascade rules.
- Seeded required SNOMED concepts and ICD codes, then inserted 5 demo mappings.

## Migration File
- [migrations/schema/011_fix_snomed_icd_map_schema.sql](../../migrations/schema/011_fix_snomed_icd_map_schema.sql)

## Demo Mappings Seeded
- `57054005` -> `I21.4` (NSTEMI)
- `441481004` -> `I50.21` (Acute systolic HF)
- `53084003` -> `J15.0` (Klebsiella pneumonia)
- `44054006` -> `E11.22` (Diabetes with CKD)
- `709044004` -> `N18.3` (CKD stage 3)

## Verification Queries
```sql
SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'snomed_icd_map'
ORDER BY ordinal_position;

SELECT snomed_code, icd_code_id, mapping_type, confidence, is_primary
FROM public.snomed_icd_map
ORDER BY snomed_code;

SELECT snomed_code, description
FROM public.snomed_concepts
WHERE snomed_code IN ('57054005','441481004','53084003','44054006','709044004');

SELECT code, description
FROM public.icd_codes
WHERE code IN ('I21.4','I50.21','J15.0','E11.22','N18.3');
```

## Outcome
- `snomed_icd_map` now uses `icd_code_id` and validates cleanly.
- Required SNOMED concepts and ICD codes exist.
- Demo mappings are present for direct SNOMED-to-ICD resolution.
