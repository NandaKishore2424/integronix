# Integronix — Database Migrations

All migrations must be run **in order** via **Supabase → SQL Editor → New Query**.
Paste each file's content and click **Run**.

---

## Phase 1 — Foundation (Run First)
*Creates the core schema. Must be done before anything else.*

| Order | File | What It Creates | Dependencies |
|---|---|---|---|
| 1 | `001_extensions.sql` | pgvector + uuid-ossp extensions | None |
| 2 | `002_create_icd_codes.sql` | ICD-10-CM master table + embedding column | 001 |
| 3 | `003_create_snomed.sql` | SNOMED concepts + SNOMED→ICD crosswalk | 002 |
| 4 | `004_create_cases.sql` | `clinical_cases` + `coding_results` | 002, 003 |
| 5 | `005_create_revenue.sql` | DRG revenue lookup per ICD code | 002 |
| 6 | `006_create_audit_log.sql` | Full pipeline audit trail table | None |
| 7 | `007_create_indexes.sql` | B-tree + IVFFlat vector indexes | 002–006 |

---

## Phase 2 — Seed Data (Run After Phase 1)
*Loads reference data into the schema. Run once only.*

| Order | File | What It Seeds | Notes |
|---|---|---|---|
| 8 | `008_seed_data.sql` | 10 ICD codes, 5 SNOMED concepts, 6 mappings | Run once — will fail on re-run |
| 9 | `009_expanded_seed.sql` | 61 more ICD codes, 12 more SNOMED, 5 more mappings | Run once after 008 |

---

## Phase 3 — Advanced Features (Run After Phase 2)
*RPC functions and vector search capabilities.*

| Order | File | What It Creates | Notes |
|---|---|---|---|
| 10 | `010_vector_search_rpc.sql` | `match_icd_codes()` pgvector RPC function | Needs IVFFlat index from 007 |

---

## Phase 4 — Multi-Tenant Architecture (Run After Phase 3)
*Adds organization, branch, and user hierarchy with data isolation.*

| Order | File | What It Creates | Dependencies |
|---|---|---|---|
| 11 | `011_create_organizations.sql` | `organizations` table (top-level tenant) | Phase 1 complete |
| 12 | `012_create_branches.sql` | `branches` table (sub-units of org) | 011 |
| 13 | `013_create_users.sql` | `users` table with role-based access | 011, 012 |
| 14 | `014_add_tenant_columns.sql` | Adds `org_id`, `branch_id`, `submitted_by` to existing tables | 011–013 |
| 15 | `015_row_level_security.sql` | Row-Level Security policies (data isolation) | 014 |
| 16 | `016_seed_demo_org.sql` | Demo hospital + 3 branches + 4 users | 015 |

---

## After Running All Migrations — Verify

Run this in the SQL editor to confirm everything is correct:

```sql
-- Check table row counts
SELECT 'organizations'    AS tbl, COUNT(*) FROM organizations
UNION ALL SELECT 'branches',         COUNT(*) FROM branches
UNION ALL SELECT 'users',            COUNT(*) FROM users
UNION ALL SELECT 'icd_codes',        COUNT(*) FROM icd_codes
UNION ALL SELECT 'snomed_concepts',  COUNT(*) FROM snomed_concepts
UNION ALL SELECT 'snomed_icd_map',   COUNT(*) FROM snomed_icd_map
UNION ALL SELECT 'revenue_lookup',   COUNT(*) FROM revenue_lookup
UNION ALL SELECT 'clinical_cases',   COUNT(*) FROM clinical_cases
UNION ALL SELECT 'coding_results',   COUNT(*) FROM coding_results
UNION ALL SELECT 'audit_log',        COUNT(*) FROM audit_log;
```

**Expected counts after all 16 migrations:**

| Table | Expected Count |
|---|---|
| organizations | 1 (City General Hospital) |
| branches | 3 (Cardiology, Endocrinology, Orthopaedics) |
| users | 4 (admin, auditor, 2 coders) |
| icd_codes | 71 |
| snomed_concepts | 17 |
| snomed_icd_map | 11 |
| revenue_lookup | varies |
| clinical_cases | 0 (empty until cases are submitted) |
| coding_results | 0 |
| audit_log | 0 |

---

## Key Rules

1. **Always 001 first** — `vector` extension must exist before any VECTOR(384) column
2. **002 and 003 before 004** — `coding_results` has FK to both `icd_codes` and `snomed_concepts`
3. **007 after seed data** — IVFFlat vector index needs rows to build efficiently
4. **008 and 009 run once only** — re-running will fail with unique constraint violations
5. **011 → 012 → 013 in order** — branches FK to organizations; users FK to both
6. **014 before 015** — RLS policies reference the columns added in 014
7. **Never put SERVICE_KEY in frontend** — only ANON_KEY. Service key bypasses RLS.

---

## Full Architecture (What Each Phase Enables)

```
Phase 1 (001–007): Schema exists, empty
Phase 2 (008–009): ICD + SNOMED reference data loaded
Phase 3 (010):     Embedding similarity search works
Phase 4 (011–016): Multi-tenant → hospital data is isolated per org
```

---

## Backend Environment Variables Needed

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=eyJ...   ← bypasses RLS, backend only
SUPABASE_ANON_KEY=eyJ...      ← RLS enforced, for frontend
GROQ_API_KEY=gsk_...
```
