# SNOMED CT Ingestion Plan (RF2 -> Database)

This document defines a production-grade plan to ingest the full SNOMED CT RF2 release into our database, map SNOMED to ICD-10-CM, and keep the data continuously updated. The goal is a rigid, auditable, and reliable clinical terminology layer that supports the existing nodes in the pipeline.

---

## 1) Objectives

- Ingest the **full SNOMED CT RF2 release** into core tables.
- Keep **concepts, descriptions, relationships, and refsets** consistent and queryable.
- Provide a **high-precision SNOMED -> ICD-10-CM mapping** table used by the pipeline.
- Support **versioned updates** and **auditability** over time.
- Guarantee deterministic behavior for the SNOMED fallback path.

---

## 2) Source of Truth

- **Source:** SNOMED CT RF2 release from SNOMED International or the local National Release Center (NRC).
- **Format:** RF2 (Release Format 2) text files, typically ZIP.
- **Key file families:**
  - Concept
  - Description
  - Relationship
  - Refset (language, module, map)

Note: Access is licensed. Ensure licensing and distribution permissions are secured before ingesting or distributing data.

---

## 3) Target Database Tables (Proposed)

### 3.1 Core SNOMED tables

- `snomed_concepts`
  - `snomed_code` (TEXT, PK)
  - `description` (TEXT)
  - `synonyms` (TEXT[])
  - `semantic_tag` (TEXT)
  - `hierarchy` (TEXT)  -- e.g., "Clinical finding"
  - `is_active` (BOOLEAN)
  - `version` (TEXT)
  - `embedding` (VECTOR(384))
  - `created_at` (TIMESTAMPTZ)

- `snomed_descriptions`
  - `id` (BIGINT, PK)
  - `concept_id` (TEXT, FK)
  - `term` (TEXT)
  - `type_id` (TEXT) -- FSN / synonym
  - `language_code` (TEXT)
  - `is_active` (BOOLEAN)
  - `effective_time` (DATE)

- `snomed_relationships`
  - `id` (BIGINT, PK)
  - `source_id` (TEXT)
  - `destination_id` (TEXT)
  - `type_id` (TEXT)
  - `relationship_group` (INT)
  - `is_active` (BOOLEAN)
  - `effective_time` (DATE)

- `snomed_refsets`
  - `id` (BIGINT, PK)
  - `refset_id` (TEXT)
  - `referenced_component_id` (TEXT)
  - `value` (TEXT)
  - `is_active` (BOOLEAN)
  - `effective_time` (DATE)

### 3.2 Mapping tables

- `snomed_icd_map`
  - `id` (BIGINT, PK)
  - `snomed_code` (TEXT, FK)
  - `icd_code` (TEXT, FK)
  - `mapping_type` (TEXT) -- exact, broader, narrower, approximate
  - `confidence` (NUMERIC)
  - `is_primary` (BOOLEAN)
  - `source` (TEXT)
  - `notes` (TEXT)

---

## 4) RF2 -> DB Ingestion Steps (Batch Plan)

### Step 1: Acquire RF2 Release

- Download the latest RF2 release package (International or local NRC).
- Store in a secure, versioned bucket:
  - `snomed/releases/2024-10/` (example)

### Step 2: Stage Raw Files

- Unzip into a staging directory:
  - `rf2/Concept/` 
  - `rf2/Description/`
  - `rf2/Relationship/`
  - `rf2/Refset/`

### Step 3: Load into Staging Tables (Raw)

- Create staging tables mirroring RF2 columns, e.g.
  - `stg_snomed_concept`
  - `stg_snomed_description`
  - `stg_snomed_relationship`
  - `stg_snomed_refset`

- Use bulk COPY or high-throughput loader to ingest.

### Step 4: Normalize into Core Tables

- Build `snomed_concepts` from:
  - active concepts only
  - primary FSN description
  - derived `semantic_tag`
- Populate `synonyms` from description table.
- Populate `hierarchy` from relationships (is-a chains).
- Index on `snomed_code`, `description`, `semantic_tag`.

### Step 5: Embeddings

- Generate embeddings for `snomed_concepts.description` using `all-MiniLM-L6-v2`.
- Store in `embedding` column.

---

## 5) Mapping Strategy: SNOMED -> ICD-10-CM

### 5.1 Mapping Sources

Use official or licensed map datasets:
- **SNOMED CT to ICD-10-CM map** (RF2 map refset).
- Optionally, local payer or custom mappings for specific insurers.

### 5.2 Mapping Types

Store mapping type and confidence:
- `exact`
- `narrower`
- `broader`
- `approximate`

### 5.3 Mapping Resolution Rules

- Prefer `exact` and `is_primary=true` when available.
- If multiple candidates exist:
  - rank by mapping type + confidence
  - keep all results, mark best as `is_primary=true`

### 5.4 Enrichment

- Join with `icd_codes` to attach:
  - billable flags
  - CC/MCC
  - base reimbursement

---

## 6) Update Strategy (Keep Data Current)

### 6.1 Versioned Releases

- Each RF2 release is treated as immutable.
- Keep a `version` label (e.g., `SNOMED-CT-2024-10`) stored with all rows.

### 6.2 Incremental Updates

- On each new release:
  - load to staging
  - compare effective_time
  - update changed concepts
  - deactivate removed concepts
  - insert new concepts

### 6.3 Mapping Updates

- Update `snomed_icd_map` using new map refsets.
- Preserve old mappings for audit history.
- Mark old mappings as inactive (or with end date).

---

## 7) Validation and Quality Gates

### Required checks

- Count validation:
  - # of active concepts
  - # of descriptions
  - # of relationships
- Coverage validation:
  - % of active concepts mapped to ICD-10
  - % of requests resolved by SNOMED path
- Integrity checks:
  - all `snomed_code` keys exist in `snomed_concepts`
  - all `icd_code` keys exist in `icd_codes`

### Runtime guards

- If `snomed_concepts` count below threshold (e.g., 100k), block ICD-10 SNOMED path and force embedding fallback.

---

## 8) Integration with Existing Nodes

- `snomed_resolver_node` uses `snomed_concepts` for validation + text fallback.
- `snomed_icd_mapping_node` uses `snomed_icd_map` to generate ICD-10 candidates.
- `icd_embedding_node` remains as semantic fallback.

This plan upgrades the SNOMED path into a production-grade resolution strategy without changing the orchestration flow.

---

## 9) Operational Notes

- **Licensing:** Ensure SNOMED CT license compliance for your region.
- **Storage:** RF2 release files should be retained for audit.
- **Monitoring:** Track fallback rate to embeddings; high rates indicate coverage issues.

---

## 10) Suggested Roadmap

1) Build RF2 staging loader + core tables
2) Load full release, validate counts
3) Ingest official SNOMED -> ICD-10 map
4) Generate embeddings
5) Implement update pipeline with versioned releases
6) Add runtime guardrails and metrics
