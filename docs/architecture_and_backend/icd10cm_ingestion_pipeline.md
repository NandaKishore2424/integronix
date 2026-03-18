# ICD-10-CM Ingestion Pipeline (FY2026)

## 1) Overview
This document describes the production-grade ICD-10-CM ingestion pipeline for FY2026. The pipeline transforms official ICD-10-CM datasets into a structured, queryable, and intelligent backend system that supports hierarchy traversal, coding rules, and semantic search.

**Objective:**
- Store all ICD codes.
- Preserve hierarchical relationships.
- Capture coding rules and annotations.
- Enable index-based search.
- Support future AI/NLP coding workflows.

---

## 2) Data Sources
All datasets are sourced from the official ICD-10-CM release (CDC/NCHS).

### 2.1 ICD Order File (TXT)
**File:** ICD-data/icd10orderfiles/icd10cm_order_2026.txt

**Contains:**
- All ICD codes
- Long descriptions
- Billable flag (not used directly; billable is computed from hierarchy)

**Format:** Fixed-width
- [1–5] Order number
- [7–13] Code (dotless)
- [15] Billable flag
- [17–76] Short description
- [78–end] Long description

### 2.2 Tabular XML
**File:** ICD-data/table-and-index/Table and Index/icd10cm_tabular_2026.xml

**Contains:**
- Chapters and sections
- Parent/child hierarchy (`<diag>` nodes)
- Coding rules (includes/excludes, codeFirst, useAdditionalCode)
- 7th character definitions

### 2.3 Index XML
**File:** ICD-data/table-and-index/Table and Index/icd10cm_index_2026.xml

**Contains:**
- Semantic search terms
- Synonyms and redirects
- Partial codes (e.g., `I63.-`)

**Important:** The index is a search layer, not strict relational data.

---

## 3) Database Design
**Database:** PostgreSQL (Supabase)

### 3.1 icd_codes
**Purpose:** Master dataset for ICD codes

**Schema:**
- `code` TEXT PRIMARY KEY
- `code_raw` TEXT
- `description` TEXT
- `chapter` TEXT
- `category` TEXT
- `is_billable` BOOLEAN
- `is_cc` BOOLEAN
- `is_mcc` BOOLEAN
- `version` TEXT
- `system` TEXT
- `base_reimbursement` NUMERIC
- `embedding` VECTOR(384)
- `created_at` TIMESTAMPTZ

### 3.2 icd_code_hierarchy
**Purpose:** Parent/child relationships

**Schema:**
- `code` TEXT (FK → icd_codes.code)
- `parent_code` TEXT
- `level` INT
- `chapter` TEXT
- `section` TEXT
- `full_path` TEXT
- `created_at` TIMESTAMPTZ

### 3.3 icd_code_metadata
**Purpose:** Coding rules and annotations

**Schema:**
- `code` TEXT (FK → icd_codes.code)
- `inclusion_terms` TEXT[]
- `excludes1` TEXT[]
- `excludes2` TEXT[]
- `notes` TEXT[]
- `created_at` TIMESTAMPTZ

### 3.4 icd_index_terms
**Purpose:** Search and semantic lookup

**Schema:**
- `id` UUID PRIMARY KEY
- `term` TEXT
- `normalized_term` TEXT
- `code` TEXT NULL (FK removed)
- `parent_term` TEXT
- `level` INT
- `is_redirect` BOOLEAN
- `redirect_to` TEXT
- `created_at` TIMESTAMPTZ

**Design decision:**
The foreign key on `icd_index_terms.code` was removed because the index contains partial codes (e.g., `I63.-`) and redirect-only entries. The index is a search layer and not a strict relational mapping.

---

## 4) Pipeline Architecture

### 4.1 Data Flow
```
TXT (order file)
   ↓ parse_icd_txt()
   ↓ icd_codes

Tabular XML
   ↓ parse_tabular_xml()
   ↓ icd_code_hierarchy
   ↓ icd_code_metadata

Index XML
   ↓ parse_index_xml()
   ↓ icd_index_terms
```

### 4.2 High-Level Stages
1. Parse TXT (codes + descriptions)
2. Parse tabular XML (hierarchy + metadata)
3. Compute billable flags from hierarchy
4. Parse index XML (search terms)
5. Batch load all outputs

---

## 5) Implementation Structure
```
backend/
 ├── services/
 │    ├── icd_parsers.py
 │    ├── icd_loader_service.py
 │    ├── icd_ingestion_service.py
 ├── scripts/
 │    └── run_icd_ingestion.py
```

---

## 6) Parsing Logic

### 6.1 parse_icd_txt()
- Reads fixed-width TXT
- Extracts `code`, `description`
- Normalizes dotless codes into dotted format
- **Note:** `is_billable` is not finalized here

### 6.2 parse_tabular_xml()
- Recursively traverses `<diag>` nodes
- Builds hierarchy rows with `parent_code`, `level`, `full_path`
- Extracts metadata:
  - `inclusion_terms`
  - `excludes1`, `excludes2`
  - `notes` (codeFirst, useAdditionalCode, codeAlso, sevenChrNote, sevenChrDef)

### 6.3 parse_index_xml()
- Recursive traversal of `<mainTerm>` and nested `<term>`
- Builds phrase from term path for normalization
- Stores raw title in `term`
- **Invalid code filter:**
  - If `code.endswith('-')` → set to `NULL`
  - Count invalid code occurrences

---

## 7) Loader Design
- Uses Supabase PostgREST client
- Batch size: 500
- Conflict handling: ignore duplicates

### Functions
- `bulk_insert_icd_codes()`
- `bulk_insert_hierarchy()`
- `bulk_insert_metadata()`
- `bulk_insert_index_terms()`

---

## 8) Billable Logic
Computed from hierarchy:
```
leaf_codes = all_codes - parent_codes
leaf → is_billable = TRUE
parent → is_billable = FALSE
```

This avoids relying on the order file’s billable flag and ensures consistency with the XML hierarchy.

---

## 9) Orchestration

### Full pipeline
`run_full_ingestion()`
- Parses and loads codes
- Parses and loads hierarchy
- Parses and loads metadata
- Marks billable flags
- Parses and loads index terms

### Index-only ingestion
```
python scripts/run_icd_ingestion.py --index-only
```

---

## 10) Validation and Logging

### Validation counts
- `icd_codes`
- `icd_code_hierarchy`
- `icd_code_metadata`
- `icd_index_terms`

### Logging
Each phase logs:
- `phase_start`
- `phase_complete`
- `phase_failed`

Index ingestion logs invalid code filtering:
- `index_invalid_codes_filtered`

---

## 11) Results (FY2026 Run)
- `icd_codes`: 98,186
- `icd_code_hierarchy`: 46,881
- `icd_code_metadata`: 46,881
- `icd_index_terms`: 70,385

**Invalid index codes filtered:** 6,955

---

## 12) System Capabilities
- Exact ICD lookup
- Hierarchical traversal
- Coding rule validation
- Semantic search mapping

Example flow:
```
Input: "typhoid"
index_terms → icd_codes → metadata
Output: A01.0 → Typhoid fever
```

---

## 13) Future Enhancements
- Search API: `GET /search?q=diabetes`
- NLP mapping pipeline
- Semantic embeddings via pgvector
- Expanded SNOMED → ICD mapping

---

## 14) Conclusion
This ingestion pipeline transforms raw ICD-10-CM datasets into a structured, searchable, healthcare-grade knowledge system. It establishes the data foundation required for clinical coding automation, compliance validation, and future AI-driven workflows.
