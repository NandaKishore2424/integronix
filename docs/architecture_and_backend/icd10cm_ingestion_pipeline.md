# ICD-10-CM Ingestion Pipeline

## 1. Overview

This document provides a comprehensive technical breakdown of the ICD-10-CM data ingestion pipeline. This pipeline is responsible for parsing official datasets from the CDC/NCHS, transforming them into a structured format, and loading them into our PostgreSQL database.

The primary goal is to create a rich, relational, and searchable dataset that powers the ICD-10-CM coding path within the main agentic workflow. This includes not just codes and descriptions, but also the hierarchy, coding rules, and a semantic search index.

The entire process is orchestrated by the script `backend/scripts/run_icd_ingestion.py`.

---

## 2. Data Sources

The pipeline consumes three distinct data files from the official US ICD-10-CM release. These files are located in the `ICD-data/` directory.

| File Name                  | Path                                       | Format        | Purpose                                                              |
| -------------------------- | ------------------------------------------ | ------------- | -------------------------------------------------------------------- |
| `icd10cm_order_2026.txt`   | `ICD-data/icd10orderfiles/`                | Fixed-width   | Provides the master list of all 98,000+ codes and their descriptions. |
| `icd10cm_tabular_2026.xml` | `ICD-data/table-and-index/Table and Index/` | XML           | Defines the complete parent-child hierarchy and associated coding rules. |
| `icd10cm_index_2026.xml`   | `ICD-data/table-and-index/Table and Index/` | XML           | Contains the alphabetical index of terms used for semantic search.   |

---

## 3. Pipeline Orchestration

The ingestion is managed by `backend/services/icd_ingestion_service.py`, which defines the sequence of operations. The `run_full_ingestion` function executes the following phases in order:

1.  **Parse & Load Codes**: Read `icd10cm_order_2026.txt` and load the initial data into the `icd_codes` table.
2.  **Parse & Load Hierarchy/Metadata**: Read `icd10cm_tabular_2026.xml` and load data into the `icd_code_hierarchy` and `icd_code_metadata` tables.
3.  **Compute & Update Billable Flags**: Analyze the hierarchy data to determine which codes are leaf nodes and update the `is_billable` flag in the `icd_codes` table.
4.  **Parse & Load Index**: Read `icd10cm_index_2026.xml` and populate the `icd_index_terms` table for search.

---

## 4. Phase 1: Parsing (`icd_parsers.py`)

The `icd_parsers.py` service is responsible for reading the raw data files and converting them into structured Python dataclasses, with no database interaction.

### `parse_icd_txt`
-   **Input**: The fixed-width `icd10cm_order_2026.txt` file.
-   **Logic**: Reads the file line by line, slicing the string at specific character positions to extract the raw code and its long description.
-   **Key Decision**: The `is_billable` flag from this file is **ignored**. The definitive billable status is calculated later from the hierarchy structure.
-   **Output**: A list of `IcdTxtRow` objects.

### `parse_tabular_xml`
-   **Input**: The `icd10cm_tabular_2026.xml` file.
-   **Logic**: This function performs a recursive walk of the XML tree, starting from `<chapter>` down through `<section>` and nested `<diag>` elements.
-   **Hierarchy**: As it traverses, it records the `parent_code` for each `code`, its `level` in the tree, and the full path.
-   **Metadata**: It also extracts critical coding rules and notes from tags like `<inclusionTerm>`, `<excludes1>`, `<excludes2>`, `<codeFirst>`, and `<useAdditionalCode>`.
-   **Output**: Two lists: `IcdHierarchyRow` objects and `IcdMetadataRow` objects.

### `parse_index_xml`
-   **Input**: The `icd10cm_index_2026.xml` file.
-   **Logic**: Recursively walks the `<mainTerm>` and nested `<term>` elements to build a semantic index. It captures the term itself, the associated ICD code (if any), and handles redirects like `<see>` and `<seeAlso>`.
-   **Key Decision**: Codes ending in a hyphen (e.g., `I63.-`) are considered invalid for direct mapping and are filtered out, though the term itself is kept for search purposes.
-   **Output**: A list of `IcdIndexRow` objects and a count of invalid codes filtered.

---

## 5. Phase 2: Loading (`icd_loader_service.py`)

This service takes the parsed dataclass objects, converts them to dictionaries, and handles the database loading logic.

### `bulk_insert_*` Functions
-   **Logic**: The loader uses a set of `bulk_insert_*` functions (e.g., `bulk_insert_icd_codes`, `bulk_insert_hierarchy`).
-   **Batching**: To handle the large volume of data efficiently, data is chunked into batches (default size: 500 rows).
-   **Mechanism**: Each batch is sent as a single `POST` request to the appropriate Supabase PostgREST endpoint (e.g., `/rest/v1/icd_codes`). This is significantly faster than inserting row by row.
-   **Conflict Handling**: The `Prefer: resolution=ignore-duplicates` header is used to prevent errors if a record already exists, making the script idempotent.

### `compute_leaf_and_parent_codes` & `update_icd_billable_flags`
This is the most critical step for ensuring data quality.
1.  **Compute**: After the entire hierarchy has been loaded, `compute_leaf_and_parent_codes` creates two sets: a set of all codes that appear as a `parent_code`, and a set of all codes that exist in the hierarchy.
2.  **Identify Leaves**: The leaf nodes are identified by taking the difference: `leaf_codes = all_codes - parent_codes`. By definition, a code that is never a parent to another code is a terminal, billable code.
3.  **Update Flags**: The `update_icd_billable_flags` function then issues batch `PATCH` requests to the `/rest/v1/icd_codes` endpoint, setting `is_billable = TRUE` for all codes in the `leaf_codes` set and `is_billable = FALSE` for all codes in the `parent_codes` set.

---

## 6. Database Schema

The pipeline populates four main tables:

-   `icd_codes`: The master table for every code, its description, and key flags (`is_billable`, `is_cc`, `is_mcc`). This is the central table used by the application.
-   `icd_code_hierarchy`: Stores the parent-child relationships, allowing for traversal of the ICD tree.
-   `icd_code_metadata`: Stores important coding rules and notes associated with each code.
-   `icd_index_terms`: A "search index" table containing keywords and phrases that map to ICD codes, used for fast lookups.

---

## 7. Execution

To run the full ingestion pipeline from scratch:
```bash
python3 backend/scripts/run_icd_ingestion.py
```
The script will provide a summary of inserted rows and validation counts upon completion.


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
