# Integronix — Database Migrations

All migrations must be run **in order** via **Supabase → SQL Editor**.

## Files

| File | What It Does |
|---|---|
| `001_extensions.sql` | Enable `vector` and `uuid-ossp` extensions |
| `002_create_icd_codes.sql` | ICD-10 master table with embedding column |
| `003_create_snomed.sql` | SNOMED concepts + SNOMED→ICD crosswalk |
| `004_create_cases.sql` | Clinical cases + coding results |
| `005_create_revenue.sql` | DRG revenue lookup table |
| `006_create_audit_log.sql` | Explainability audit log (every node decision) |
| `007_create_indexes.sql` | All indexes including ivfflat for vector search |
| `008_seed_data.sql` | 10 ICD codes, 5 SNOMED concepts, 6 mappings |

## Rules

1. Always run 001 first — no other migration will work without extensions
2. Run 002 and 003 before 004 (foreign key dependencies)
3. Run 007 (indexes) AFTER 008 (seed data) — ivfflat needs rows to build efficiently
4. Never re-run 008 — it will fail with unique constraint violations

## Verify After Running All

```sql
SELECT 'icd_codes' as tbl, COUNT(*) FROM icd_codes
UNION ALL SELECT 'snomed_concepts', COUNT(*) FROM snomed_concepts
UNION ALL SELECT 'snomed_icd_map',  COUNT(*) FROM snomed_icd_map
UNION ALL SELECT 'clinical_cases',  COUNT(*) FROM clinical_cases
UNION ALL SELECT 'coding_results',  COUNT(*) FROM coding_results
UNION ALL SELECT 'audit_log',       COUNT(*) FROM audit_log;
```

Expected:
```
icd_codes       | 10
snomed_concepts | 5
snomed_icd_map  | 6
clinical_cases  | 0
coding_results  | 0
audit_log       | 0
```
