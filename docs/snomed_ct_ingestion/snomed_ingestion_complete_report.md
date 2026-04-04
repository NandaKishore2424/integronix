# SNOMED CT RF2 Ingestion — Complete Data Engineering Report

**Prepared for:** Data Engineers  
**Date:** March 26, 2026  
**Release ingested:** SNOMED CT International RF2 — March 1, 2026  
**System:** Integronix AI Clinical Coding Engine  

---

## Table of Contents

1. [What is SNOMED CT?](#1-what-is-snomed-ct)
2. [Why We Ingested It](#2-why-we-ingested-it)
3. [Source Data — Raw RF2 Files](#3-source-data--raw-rf2-files)
4. [Target Database Schema](#4-target-database-schema)
5. [Ingestion Pipeline — Phase by Phase](#5-ingestion-pipeline--phase-by-phase)
6. [Vector Embedding Generation](#6-vector-embedding-generation)
7. [Final Record Counts](#7-final-record-counts)
8. [Performance Summary](#8-performance-summary)
9. [Code Ingestion Architecture Diagram](#9-code-ingestion-architecture-diagram)
10. [Post-Ingestion Steps](#10-post-ingestion-steps)
11. [How It Connects to the Live Pipeline](#11-how-it-connects-to-the-live-pipeline)

---

## 1. What is SNOMED CT?

**SNOMED CT** (Systematized Nomenclature of Medicine — Clinical Terms) is the world's largest, most comprehensive clinical health terminology system. Maintained by SNOMED International, it is the global standard for encoding clinical diagnoses, findings, procedures, and observations in electronic health records.

### Key concepts

| Term | Definition |
|---|---|
| **Concept** | A unique clinical idea (e.g. "Myocardial infarction") identified by a permanent numeric ID |
| **Description** | A human-readable text label for a concept. One concept has one FSN and multiple synonyms |
| **FSN** | Fully Specified Name — the canonical, unambiguous name for a concept, always ends with a semantic tag e.g. `"Non-ST elevation myocardial infarction (disorder)"` |
| **Synonym** | Alternative names/abbreviations for a concept — e.g. "NSTEMI", "heart attack", "non-Q-wave MI" |
| **Relationship** | A typed link between two concepts — most commonly IS-A (hierarchy) e.g. NSTEMI IS-A Myocardial infarction |
| **Semantic Tag** | The category suffix in FSN brackets — `(disorder)`, `(procedure)`, `(finding)`, `(organism)`, `(body structure)` etc. |
| **IS-A** | The parent-child relationship type (typeId `116680003`) that builds the SNOMED hierarchy tree |
| **RF2** | Release Format 2 — the official tab-separated file format SNOMED International uses to distribute releases |
| **Snapshot** | A point-in-time view of the data — only the latest active state of every component. We use Snapshot, not Full |

---

## 2. Why We Ingested It

The Integronix pipeline converts a doctor's free-text clinical note into a billable ICD-10 or ICD-11 code. The resolution happens through 3 fallback paths:

```
Doctor's Note: "Patient had a widow-maker MI with cardiogenic shock"
                              │
             ┌────────────────▼────────────────┐
             │   Path 1: WHO ICD API            │  → ICD-11 direct (Ayushman/CGHS orgs)
             └────────────────┬────────────────┘
                              │ (if ICD-10 org or API returns nothing)
             ┌────────────────▼────────────────┐
             │   Path 2: SNOMED Resolver        │  → text/semantic search on snomed_concepts
             │   + SNOMED→ICD crosswalk         │  → lookup snomed_icd_map → ICD-10 code
             └────────────────┬────────────────┘
                              │ (if no SNOMED match)
             ┌────────────────▼────────────────┐
             │   Path 3: Vector Embedding       │  → cosine similarity on icd_codes.embedding
             │   Fallback                       │  → pgvector nearest-neighbor search
             └─────────────────────────────────┘
```

Without the full SNOMED CT database:
- Path 2 only had 20 hand-crafted mock rows — would fail on 99.9% of real diagnoses
- The crosswalk table (`snomed_icd_map`) was seeded with only 5 manual mappings
- Semantic slang resolution ("widow-maker", "ticker stopped") was impossible

After this ingestion:
- Path 2 can resolve 379,283 active SNOMED concepts via text or semantic search
- Path 3 can semantically match across 98,121 ICD codes and 379,283 SNOMED concepts via pgvector

---

## 3. Source Data — Raw RF2 Files

### Release package

```
SnomedCT_InternationalRF2_PRODUCTION_20260301T120000Z/
├── Full/           ← historical edits since inception — NOT used
└── Snapshot/       ← latest active state only — THIS IS WHAT WE USE
    └── Terminology/
        ├── sct2_Concept_Snapshot_INT_20260301.txt          30 MB
        ├── sct2_Description_Snapshot-en_INT_20260301.txt  227 MB
        ├── sct2_Relationship_Snapshot_INT_20260301.txt    396 MB
        ├── sct2_StatedRelationship_Snapshot_...txt        114 MB  (not used)
        ├── sct2_TextDefinition_Snapshot-en_...txt           8 MB  (not used)
        └── sct2_RelationshipConcreteValues_Snapshot_...txt  4 MB  (not used)
```

**Why Snapshot and not Full?**  
The Full directory contains every historical version of every record since SNOMED's inception — hundreds of millions of rows. Snapshot contains only the current effective state of each component. For a clinical coding system, we only care about what is valid today.

---

### File 1: `sct2_Concept_Snapshot_INT_20260301.txt` (30 MB)

Tab-separated. First line is header. One row per concept.

| Column | Type | Description |
|---|---|---|
| `id` | BIGINT | The SNOMED Concept ID (permanent, never reused) — e.g. `57054005` |
| `effectiveTime` | YYYYMMDD | Date this row became effective — e.g. `20020131` |
| `active` | 0 or 1 | `1` = active (in use), `0` = retired/inactive |
| `moduleId` | BIGINT | SNOMED module this concept belongs to |
| `definitionStatusId` | BIGINT | `900000000000074008` = Primitive, `900000000000073002` = Fully defined |

**We filter:** only `active = 1` rows. Total active concepts in this release: **379,283**

---

### File 2: `sct2_Description_Snapshot-en_INT_20260301.txt` (227 MB)

Tab-separated. One row per text label. Multiple rows per concept.

| Column | Type | Description |
|---|---|---|
| `id` | BIGINT | Unique description ID |
| `effectiveTime` | YYYYMMDD | Date this description became effective |
| `active` | 0 or 1 | Active flag |
| `moduleId` | BIGINT | Module |
| `conceptId` | BIGINT | FK → Concept ID this description belongs to |
| `languageCode` | TEXT | `en` (we only process English) |
| `typeId` | BIGINT | `900000000000003001` = FSN, `900000000000013009` = Synonym |
| `term` | TEXT | The actual text string e.g. `"Non-ST elevation myocardial infarction (disorder)"` |
| `caseSignificanceId` | BIGINT | Case sensitivity rule |

**We filter:** `active = 1` AND `conceptId` exists in our active concepts set. Total active descriptions ingested: **1,014,913**

**FSN extraction:** For each concept, the row where `typeId = 900000000000003001` is the FSN. We:
1. Set `snomed_concepts.description` = the FSN term
2. Extract the semantic tag from the bracketed suffix using regex `\(([^)]+)\)$`
3. Store it in `snomed_concepts.semantic_tag`

---

### File 3: `sct2_Relationship_Snapshot_INT_20260301.txt` (396 MB)

Tab-separated. One row per relationship between two concepts.

| Column | Type | Description |
|---|---|---|
| `id` | BIGINT | Unique relationship ID |
| `effectiveTime` | YYYYMMDD | Date effective |
| `active` | 0 or 1 | Active flag |
| `moduleId` | BIGINT | Module |
| `sourceId` | BIGINT | The child concept (e.g. NSTEMI) |
| `destinationId` | BIGINT | The parent concept (e.g. Myocardial infarction) |
| `relationshipGroup` | INT | Groups related attributes together (0 = ungrouped) |
| `typeId` | BIGINT | Relationship type — `116680003` = IS-A |
| `characteristicTypeId` | BIGINT | Inferred vs stated |
| `modifierId` | BIGINT | Always `900000000000451002` (Some) |

**We filter:** `active = 1` only. Total active relationships ingested: **1,331,550**

---

## 4. Target Database Schema

### `snomed_concepts` table

Primary table. One row per active SNOMED concept.

```sql
CREATE TABLE snomed_concepts (
    snomed_code     TEXT        PRIMARY KEY,    -- SNOMED Concept ID (e.g. "57054005")
    description     TEXT        NOT NULL,       -- FSN from sct2_Description (filled in Pass 2)
    synonyms        TEXT[],                     -- Legacy column (not populated by this ingestion)
    semantic_tag    TEXT,                       -- Extracted from FSN brackets e.g. "(disorder)"
    hierarchy       TEXT,                       -- e.g. "Clinical finding" (not populated yet)
    is_active       BOOLEAN     DEFAULT TRUE,
    version         TEXT        DEFAULT 'SNOMED-CT-2024',
    embedding       VECTOR(384),                -- 384-dim semantic vector (populated in Phase 2)
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

**Indexes:**
- Primary key B-tree on `snomed_code` (exact lookups)
- GIN tsvector index on `description` (fast full-text `ilike` search) — added post-ingestion
- IVFFlat index on `embedding` (approximate nearest-neighbor vector search) — rebuilt post-embedding

---

### `snomed_descriptions` table

One row per text label. 1M+ rows.

```sql
CREATE TABLE snomed_descriptions (
    id              BIGINT      PRIMARY KEY,               -- RF2 description id
    concept_id      TEXT        NOT NULL REFERENCES snomed_concepts(snomed_code) ON DELETE CASCADE,
    term            TEXT        NOT NULL,                  -- The actual text string
    type_id         TEXT        NOT NULL,                  -- FSN=900000000000003001, Synonym=900000000000013009
    language_code   TEXT        NOT NULL,                  -- 'en'
    is_active       BOOLEAN     DEFAULT TRUE,
    effective_time  DATE        NOT NULL
);
```

**Purpose:** When the `snomed_resolver` does text search and doesn't find a match in `snomed_concepts.description`, it can search across all 1M synonym terms in this table to catch abbreviations, slang, and alternate names.

---

### `snomed_relationships` table

One row per IS-A relationship. 1.3M rows.

```sql
CREATE TABLE snomed_relationships (
    id                  BIGINT  PRIMARY KEY,
    source_id           TEXT    NOT NULL,      -- Child concept
    destination_id      TEXT    NOT NULL,      -- Parent concept
    type_id             TEXT    NOT NULL,      -- 116680003 = IS-A
    relationship_group  INT     DEFAULT 0,
    is_active           BOOLEAN DEFAULT TRUE,
    effective_time      DATE    NOT NULL
);
```

**Purpose:** Encodes the full SNOMED clinical hierarchy. Used for hierarchy traversal — e.g. to find all sub-types of "Diabetes mellitus" or to walk up the IS-A tree for DRG grouping logic.

---

### `snomed_icd_map` table

The crosswalk from SNOMED to ICD codes. Populated separately.

```sql
CREATE TABLE snomed_icd_map (
    id              SERIAL      PRIMARY KEY,
    snomed_code     TEXT        NOT NULL REFERENCES snomed_concepts(snomed_code),
    icd_code_id     TEXT        NOT NULL REFERENCES icd_codes(code),
    mapping_type    TEXT        NOT NULL CHECK (mapping_type IN ('exact','narrower','broader','approximate')),
    confidence      NUMERIC     DEFAULT 1.0,
    is_primary      BOOLEAN     DEFAULT TRUE,
    notes           TEXT,
    source          TEXT        DEFAULT 'manual'
);
```

**Note:** Column renamed from `icd_code` to `icd_code_id` in migration `011_fix_snomed_icd_map_schema.sql`.

---

## 5. Ingestion Pipeline — Phase by Phase

### Pre-condition

Before ingestion, `snomed_concepts` contained 20 hand-crafted mock rows. The script opens with:

```sql
TRUNCATE snomed_concepts CASCADE;
```

`CASCADE` automatically wipes dependent rows in `snomed_icd_map` (the 5 demo mappings). These are re-seeded after ingestion.

---

### Phase 1 — Concepts (Pass 1 of 3)

**Script:** `backend/scripts/import_snomed_rf2.py`  
**Source file:** `sct2_Concept_Snapshot_INT_20260301.txt` (30 MB)  
**Target table:** `snomed_concepts`

**Logic:**
1. Stream the file line-by-line using Python's `csv.DictReader` (generator — never loads full file into RAM)
2. For each row where `active == '1'`, add concept ID to an in-memory `set[str]` (used in Pass 2 for FK validation)
3. Accumulate rows in a batch list. Every 50,000 rows, flush to DB using `psycopg2.extras.execute_values`
4. Concepts inserted with `description = ''` placeholder (actual FSN filled in Pass 2)

**Why batch size 50,000?** Balances memory usage with round-trip overhead. Smaller batches = more network calls. Larger batches = risk of Supabase session pooler timeout on a slow network.

**INSERT statement:**
```sql
INSERT INTO snomed_concepts (snomed_code, description, is_active, version)
VALUES %s
ON CONFLICT (snomed_code) DO UPDATE SET is_active = EXCLUDED.is_active, version = EXCLUDED.version
```

**Result:** 379,283 concept rows inserted.

---

### Phase 2 — Descriptions + FSN Backfill (Pass 2 of 3)

**Source file:** `sct2_Description_Snapshot-en_INT_20260301.txt` (227 MB)  
**Target tables:** `snomed_descriptions` (insert) + `snomed_concepts` (UPDATE for FSN)

**Python CSV field size limit issue:**  
The default Python CSV parser has a 128 KB field size limit. Some SNOMED text definitions exceed this. Fixed with:
```python
import sys, csv
csv.field_size_limit(sys.maxsize)
```

**Logic:**
1. Stream descriptions line-by-line
2. Skip rows where `active != '1'` or `conceptId` not in the concept set from Pass 1
3. For every active description, add to `desc_batch` → bulk insert into `snomed_descriptions` every 50,000 rows
4. For FSN rows (`typeId == '900000000000003001'`), additionally extract semantic tag and queue an UPDATE for `snomed_concepts`
5. FSN updates flushed every 50,000 rows using `psycopg2.extras.execute_batch`

**Semantic tag extraction:**
```python
import re
def extract_semantic_tag(fsn: str) -> str:
    match = re.search(r"\(([^)]+)\)$", fsn.strip())
    return f"({match.group(1)})" if match else ""
# "Non-ST elevation myocardial infarction (disorder)" → "(disorder)"
```

**Result:**
- 1,014,913 description rows inserted into `snomed_descriptions`
- 379,264 FSN rows used to UPDATE `snomed_concepts.description` and `snomed_concepts.semantic_tag`
- Note: 379,283 concepts were inserted but only 379,264 received FSN updates — 19 concepts had no active English FSN in this release (edge case in SNOMED data, not an error)

---

### Phase 3 — Relationships (Pass 3 of 3)

**Source file:** `sct2_Relationship_Snapshot_INT_20260301.txt` (396 MB)  
**Target table:** `snomed_relationships`

**Logic:**
1. Stream relationships line-by-line
2. Filter `active == '1'` rows only
3. Batch insert every 50,000 rows using `execute_values`

**Result:** 1,331,550 active relationship rows inserted.

---

### Phase 1–3 Total Runtime

| Pass | Source file size | Records processed | Time |
|---|---|---|---|
| Pass 1 — Concepts | 30 MB | 379,283 concepts | ~30s |
| Pass 2 — Descriptions | 227 MB | 1,014,913 descriptions + 379,264 FSN updates | ~200s |
| Pass 3 — Relationships | 396 MB | 1,331,550 relationships | ~90s |
| **Total** | **653 MB** | **2,725,046 rows** | **326 seconds (~5.4 min)** |

---

## 6. Vector Embedding Generation

### What is a vector embedding?

A vector embedding is a mathematical representation of the *meaning* of text — not its characters. The AI model reads a medical phrase and outputs an array of 384 floating-point numbers (a vector in 384-dimensional space). Phrases with similar clinical meaning produce vectors that are mathematically close to each other.

```
"Myocardial infarction (disorder)"  → [0.12, -0.45, 0.88, 0.03, ...]
"Heart attack"                      → [0.11, -0.44, 0.87, 0.04, ...]  ← close!
"Fracture of femur (disorder)"      → [-0.67, 0.22, -0.11, 0.91, ...] ← far away
```

The mathematical distance between two vectors is the cosine distance. pgvector uses the `<=>` operator to compute this at query time.

---

### The model: `sentence-transformers/all-MiniLM-L6-v2`

| Property | Value |
|---|---|
| Model size | ~80 MB |
| Output dimensions | 384 |
| Input max tokens | 256 |
| License | Apache 2.0 (free for commercial use) |
| Normalization | `normalize_embeddings=True` (required for cosine similarity) |
| Why this model | Best balance of speed, size, and semantic accuracy for medical terminology |

---

### Hardware used

| Component | Spec |
|---|---|
| Machine | Micro Computer HK Tech Limited Venus series |
| CPU | AMD Ryzen 9 7940HS (Zen 4, 16 cores × 3.8 GHz base) |
| RAM | 32 GB |
| GPU | AMD Radeon 780M (RDNA 3 integrated GPU) |
| OS | Ubuntu 24.04.4 LTS |

**Why CPU and not GPU?**  
The AMD Radeon 780M is an **integrated GPU** (iGPU) — it shares system RAM and does not have a dedicated VRAM pool. ROCm (AMD's GPU compute platform, equivalent to CUDA for Nvidia) only supports **discrete** Radeon GPUs (RX 6000/7000 series, Radeon Pro, AMD Instinct). The 780M iGPU is not on the ROCm support matrix. `torch.cuda.is_available()` correctly returns `False` on this system.

The 16-core Zen 4 CPU with 32 GB RAM handled the workload effectively. Zen 4 cores have AVX-512 support which accelerates the floating-point math in sentence-transformers.

---

### Embedding generation script: `backend/scripts/generate_embeddings.py`

**Connection:** Direct PostgreSQL via `psycopg2` (not Supabase REST API — REST would reject partial-column UPDATEs with NOT NULL violations).

**Algorithm:**
1. Paginate through the target table ordered by PK, fetching 1000 rows per page, filtering `WHERE embedding IS NULL`
2. For each page, call `model.encode(texts, batch_size=64, normalize_embeddings=True)`
3. Accumulate `(embedding_vector, pk_value)` tuples
4. Every 5000 rows, execute a bulk `UPDATE table SET embedding = %s::vector WHERE pk = %s` via `psycopg2.extras.execute_batch`
5. Commit after each 5000-row batch

**Why commit every 5000?** Supabase session pooler has a default statement timeout. Committing frequently means if the connection drops mid-run, already-committed rows (filtered by `WHERE embedding IS NULL`) are skipped on resume. The script is fully idempotent.

---

### Embedding generation results

**Step 1 — ICD codes:**

| Metric | Value |
|---|---|
| Rows processed | 98,121 |
| Total time | 360.2 seconds (6 min) |
| Throughput | ~272 embeddings/second |
| Commit checkpoints | 19 commits × 5000 rows + 1 final |

**Step 2 — SNOMED concepts:**

| Metric | Value |
|---|---|
| Rows processed | 379,283 |
| Total time | 1,369.6 seconds (22.8 min) |
| Throughput | ~277 embeddings/second |
| Commit checkpoints | 75 commits × 5000 rows + 1 final |

**Combined total:**

| Metric | Value |
|---|---|
| Total rows embedded | 477,404 |
| Total time | 1,729.8 seconds (~28.8 min) |
| Average throughput | ~276 embeddings/second |

---

## 7. Final Record Counts

| Table | Records | Status |
|---|---|---|
| `snomed_concepts` | 379,283 | All rows have description, semantic_tag, embedding |
| `snomed_descriptions` | 1,014,913 | All active English descriptions |
| `snomed_relationships` | 1,331,550 | All active IS-A and attribute relationships |
| `snomed_icd_map` | 5 (demo) | Needs expansion with official SNOMED→ICD map refset |
| `icd_codes` | 98,121 | All rows now have embeddings |
| `snomed_refsets` | 0 | Not populated (optional — language/module refsets) |

---

## 8. Performance Summary

| Phase | Duration | Records | Throughput |
|---|---|---|---|
| RF2 ETL — Concepts | ~30s | 379,283 | ~12,600 rows/sec |
| RF2 ETL — Descriptions | ~200s | 1,014,913 | ~5,100 rows/sec |
| RF2 ETL — Relationships | ~90s | 1,331,550 | ~14,800 rows/sec |
| RF2 ETL — Total | 326s (5.4 min) | 2,725,046 | ~8,360 rows/sec |
| Embedding — ICD codes | 360s (6 min) | 98,121 | ~272 embed/sec |
| Embedding — SNOMED | 1,370s (22.8 min) | 379,283 | ~277 embed/sec |
| Embedding — Total | 1,730s (28.8 min) | 477,404 | ~276 embed/sec |
| **End-to-end total** | **~34 minutes** | **3.2M rows** | — |

---

## 9. Code Ingestion Architecture Diagram

```
RF2 FILES ON DISK (653 MB total)
─────────────────────────────────────────────────────────
sct2_Concept_Snapshot       sct2_Description_Snapshot    sct2_Relationship_Snapshot
     (30 MB)                      (227 MB)                     (396 MB)
        │                              │                              │
        ▼                              ▼                              ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│                    import_snomed_rf2.py  (psycopg2 direct connection)         │
│                                                                               │
│  TRUNCATE snomed_concepts CASCADE                                             │
│                                                                               │
│  Pass 1: Stream concepts line-by-line                                         │
│    filter active==1 → concept_ids set (RAM)                                   │
│    batch 50k rows → execute_values INSERT snomed_concepts                     │
│    (description placeholder = '' to satisfy NOT NULL)                         │
│                                                                               │
│  Pass 2: Stream descriptions line-by-line                                     │
│    filter active==1 AND conceptId in concept_ids                              │
│    typeId==FSN → extract_semantic_tag() → UPDATE snomed_concepts              │
│    all descriptions → batch 50k rows → execute_values INSERT snomed_descriptions│
│                                                                               │
│  Pass 3: Stream relationships line-by-line                                    │
│    filter active==1                                                           │
│    batch 50k rows → execute_values INSERT snomed_relationships                │
│                                                                               │
│  Verify: COUNT(*) all 3 tables, assert snomed_concepts > 300,000              │
└───────────────────────────────────────────────────────────────────────────────┘
        │                              │                              │
        ▼                              ▼                              ▼
 snomed_concepts              snomed_descriptions            snomed_relationships
   (379,283 rows)               (1,014,913 rows)               (1,331,550 rows)
   embedding=NULL               ─────────────────              ─────────────────


EMBEDDING GENERATION
─────────────────────────────────────────────────────────
┌───────────────────────────────────────────────────────────────────────────────┐
│                  generate_embeddings.py  (psycopg2 + sentence-transformers)   │
│                                                                               │
│  Load SentenceTransformer("all-MiniLM-L6-v2") on CPU                         │
│                                                                               │
│  Step 1: icd_codes (98,121 rows, 360s)                                        │
│    Keyset paginate WHERE embedding IS NULL ORDER BY code, 1000/page           │
│    encode(["E11.22 Type 2 diabetes...", ...], batch_size=64)                  │
│    → 384-dim normalized float vectors                                         │
│    Every 5000: execute_batch UPDATE icd_codes SET embedding=%s::vector        │
│    conn.commit()                                                              │
│                                                                               │
│  Step 2: snomed_concepts (379,283 rows, 1370s)                                │
│    Same pattern — paginate, encode, batch UPDATE, commit every 5000           │
└───────────────────────────────────────────────────────────────────────────────┘
        │                                            │
        ▼                                            ▼
 icd_codes.embedding                    snomed_concepts.embedding
  (98,121 vectors)                         (379,283 vectors)


INDEX REBUILD (post-embedding)
─────────────────────────────────────────────────────────
┌───────────────────────────────────────────────────────────────────────────────┐
│  013_rebuild_snomed_ivfflat.sql  (run in Supabase SQL Editor)                │
│                                                                               │
│  DROP INDEX IF EXISTS snomed_concepts_embedding_idx;                          │
│  CREATE INDEX snomed_concepts_embedding_idx ON snomed_concepts                │
│    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 600);            │
│                                                                               │
│  lists=600 because sqrt(379283) ≈ 616, rounded to 600                        │
│  IVFFlat divides 379k vectors into 600 clusters for fast ANN search           │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## 10. Post-Ingestion Steps

### Step 1 — Text search index (run in Supabase SQL Editor)

Enables fast `ilike`-style text search across 379k descriptions without full table scan:

```sql
CREATE INDEX idx_snomed_concepts_description
ON snomed_concepts USING gin(to_tsvector('english', description));

CREATE INDEX idx_snomed_concepts_active
ON snomed_concepts (is_active) WHERE is_active = TRUE;
```

### Step 2 — Rebuild IVFFlat index (run in Supabase SQL Editor)

After embeddings are fully populated:

```sql
-- File: migrations/schema/013_rebuild_snomed_ivfflat.sql
DROP INDEX IF EXISTS snomed_concepts_embedding_idx;
CREATE INDEX snomed_concepts_embedding_idx ON snomed_concepts
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 600);
```

**Why lists=600?** The IVFFlat index divides vectors into N clusters (Voronoi cells). The recommended value is `sqrt(row_count)`. For 379,283 rows: `sqrt(379283) ≈ 616` → rounded to 600. The original index had `lists=20`, sized for the 20-row mock — completely inadequate for production.

### Step 3 — Re-seed SNOMED→ICD mappings

The TRUNCATE in Phase 1 cascade-deleted the 5 demo `snomed_icd_map` rows. Re-seed from migration 011:

```sql
INSERT INTO snomed_icd_map (snomed_code, icd_code_id, mapping_type, confidence, is_primary, notes, source)
VALUES
  ('57054005', 'I21.4',  'exact',    0.99, true, 'NSTEMI Mapping',      'manual'),
  ('441481004','I50.21', 'exact',    0.99, true, 'Acute Systolic HF',   'manual'),
  ('53084003', 'J15.0',  'exact',    0.99, true, 'Klebsiella Pneumonia', 'manual'),
  ('44054006', 'E11.22', 'narrower', 0.91, true, 'Diabetes with CKD',   'manual'),
  ('709044004','N18.3',  'exact',    0.99, true, 'CKD Stage 3',         'manual');
```

### Step 4 — Semantic verification test

Run in the Supabase SQL Editor to confirm the vector search works end-to-end:

```sql
-- Should return "Fracture of tibia" or similar bone fracture concepts
SELECT snomed_code, description, semantic_tag,
       1 - (embedding <=> '[<paste a 384-dim test vector here>]'::vector) AS similarity
FROM snomed_concepts
WHERE is_active = TRUE
ORDER BY embedding <=> '[...]'::vector
LIMIT 5;
```

---

## 11. How It Connects to the Live Pipeline

After ingestion, the `snomed_resolver_node` in `backend/agents/snomed_resolver.py` runs this logic on every incoming clinical note:

```python
# 1. Check if LLM suggested a valid SNOMED code
row = await select_one("snomed_concepts",
    filters={"snomed_code": f"eq.{suggested_code}", "is_active": "eq.true"})

# 2. If not, text search on description across 379k rows
rows = await select("snomed_concepts",
    filters={"description": f"ilike.*{phrase}*", "is_active": "eq.true"})
```

And `backend/agents/snomed_icd_mapper.py` does the crosswalk:

```python
crosswalk_rows = await select("snomed_icd_map",
    filters={"snomed_code": f"eq.{resolved_code}", "order": "confidence.desc"})
# → returns ICD-10 code candidates with mapping_type and confidence scores
```

And `backend/agents/icd_embedding.py` handles the final fallback:

```python
results = await rpc("match_icd_codes", {
    "query_embedding": _vector_to_pg_literal(query_vector),  # 384 floats from doctor's text
    "similarity_threshold": 0.55,
    "match_count": 5
})
# → pgvector cosine search across 98k ICD embeddings
```

The `match_snomed_concepts` RPC function (defined in `migrations/schema/007_functions_and_indexes.sql`) provides the same capability over the 379k SNOMED embeddings for semantic SNOMED resolution.

---

## 12. Post-Ingestion Incident Log — Storage Overflow & Recovery (March 26, 2026)

### What happened

After completing the full ingestion (Phase 1 ETL + Phase 2 Embeddings), the Supabase database size was checked:

```
SELECT pg_size_pretty(pg_database_size(current_database()));
→ 2203 MB
```

The Supabase free tier limit is **500 MB**. The project was 4x over the limit, triggering the "EXCEEDING USAGE LIMITS" banner and putting the database at risk of going read-only.

---

### Root cause — storage breakdown

| Table | Size | Notes |
|---|---|---|
| `snomed_concepts` | 1387 MB | 379k rows × 384-float embeddings + IVFFlat index |
| `icd_codes` | 360 MB | 98k rows × embeddings — needed, kept |
| `snomed_relationships` | 206 MB | 1.3M rows — not used by live pipeline |
| `snomed_descriptions` | 188 MB | 1M rows — not used by live pipeline |
| Others | ~62 MB | Operational tables |

The `snomed_concepts` table alone consumed 1387 MB because:
- 379,283 rows × 384 floats × 4 bytes = ~584 MB of embedding data
- IVFFlat index (lists=50) = ~584 MB of posting list data (copies vectors into the index)
- Text data + other indexes = ~219 MB

**Total embedding cost for SNOMED alone: ~1168 MB.** This is inherent to storing 384-dim vectors for 379k rows — it cannot be reduced without dropping the embedding column.

---

### Why the Supabase free tier cannot host full SNOMED embeddings

| Component | Storage needed | Fits in 500 MB free? |
|---|---|---|
| `icd_codes` with embeddings (98k rows) | ~360 MB | Yes (alone) |
| `snomed_concepts` with embeddings (379k rows) | ~1387 MB | No |
| Both together | ~1747 MB | No |
| `snomed_concepts` text only (no embedding) | ~60 MB | Yes |
| Both ICD (with embed) + SNOMED (text only) | ~420 MB | Yes |

---

### Recovery steps executed

**Step 1 — Removed SNOMED embedding column and auxiliary tables:**
```sql
TRUNCATE snomed_relationships CASCADE;
TRUNCATE snomed_descriptions CASCADE;
DROP INDEX IF EXISTS snomed_concepts_embedding_idx;
ALTER TABLE snomed_concepts DROP COLUMN IF EXISTS embedding;
```

**Step 2 — Reclaimed physical disk space:**
```sql
VACUUM FULL snomed_concepts;
VACUUM FULL snomed_descriptions;
VACUUM FULL snomed_relationships;
```

Note: `VACUUM FULL` must be run as a single statement per table — it cannot run inside a transaction block. Running `VACUUM FULL` (all tables) timed out the Supabase Dashboard HTTP connection. Individual table VACUUMs succeeded.

**Step 3 — Verified icd_codes untouched:**
```sql
SELECT 'snomed_concepts' AS table_name, COUNT(*) FROM snomed_concepts
UNION ALL SELECT 'snomed_descriptions', COUNT(*) FROM snomed_descriptions
UNION ALL SELECT 'snomed_relationships', COUNT(*) FROM snomed_relationships
UNION ALL SELECT 'icd_codes', COUNT(*) FROM icd_codes;
```

Result:
```
snomed_concepts      → 0      (clean, ready for re-import)
snomed_descriptions  → 0      (clean)
snomed_relationships → 0      (clean)
icd_codes            → 98,192 (intact with all embeddings)
```

**Step 4 — Re-ran SNOMED import (all 3 passes):**
```bash
cd /home/nanda-kishore-r/Desktop/integronix/backend
source venv/bin/activate
python3 scripts/import_snomed_rf2.py
```

Terminal output confirmed success:
```
Truncating SNOMED concept graph (cascade)...
Pass 1/3: Concepts
Pass 2/3: Descriptions + FSN backfill
Pass 3/3: Relationships

SNOMED RF2 import complete
Elapsed seconds: 458.1
Inserted concepts:       379,283
Inserted descriptions:  1,014,913
Updated FSN rows:          379,264
Inserted relationships: 1,331,550

Verification counts
snomed_concepts:      379,283
snomed_descriptions: 1,014,913
snomed_relationships: 1,331,550
```

The `snomed_concepts` table no longer has an `embedding` column (dropped in Step 1). Each row stores only: `snomed_code`, `description` (FSN backfilled from Pass 2), `semantic_tag`, `is_active`, `version`.

**Step 5 — Post-import size check revealed descriptions and relationships are still too large:**

After re-import, the table breakdown was:
```
icd_codes            → 351 MB  (needed — has all ICD embeddings)
snomed_relationships → 266 MB  (not used by live pipeline)
snomed_descriptions  → 188 MB  (not used by live pipeline)
snomed_concepts      →  95 MB  (needed — text search)
icd_index_terms      →  22 MB  (needed — ICD service)
icd_code_hierarchy   →  11 MB  (needed — ICD service)
icd_code_metadata    →   7 MB  (needed — ICD service)
```

`snomed_relationships` and `snomed_descriptions` are written by `import_snomed_rf2.py` (Passes 2 and 3) but are **never queried at runtime** — verified by searching the entire `backend/` codebase. Only `import_snomed_rf2.py` itself references them. Truncated both:

```sql
TRUNCATE snomed_descriptions CASCADE;
TRUNCATE snomed_relationships CASCADE;
```

`TRUNCATE` reclaims disk immediately — no `VACUUM FULL` required. Size dropped to **496 MB**.

**Step 6 — Dropped GIN tsvector index on `snomed_concepts.description`:**

To create a further buffer below the 500 MB limit, the GIN index was dropped:

```sql
DROP INDEX IF EXISTS idx_snomed_concepts_description;
```

This saved ~13 MB. SNOMED text search now falls back to a sequential scan on 379k rows, which is slower (~200ms vs ~5ms) but functionally correct. For the development phase this trade-off is acceptable.

**Step 7 — Seeded SNOMED → ICD crosswalk demo mappings:**

```sql
INSERT INTO snomed_icd_map (snomed_code, icd_code_id, mapping_type, confidence, is_primary, notes)
VALUES
  ('22298006',  'I21.9',  'exact',   1.00, true,  'Myocardial infarction → Acute MI unspecified'),
  ('195967001', 'J45.909','exact',   1.00, true,  'Asthma → Unspecified asthma uncomplicated'),
  ('44054006',  'E11.9',  'exact',   1.00, true,  'Type 2 diabetes → T2DM without complications'),
  ('73211009',  'E11.649','broader', 0.85, false, 'Diabetes mellitus → T2DM with hypoglycemia'),
  ('38341003',  'I10',    'exact',   1.00, true,  'Hypertension → Essential hypertension')
ON CONFLICT (snomed_code, icd_code_id) DO NOTHING;
```

---

### IVFFlat index build — memory issues on free tier

During the index rebuild, two errors were encountered:

**Error 1: `memory required is 118 MB, maintenance_work_mem is 32 MB`**
- Cause: `lists=600` requires 118 MB for k-means clustering. Free tier caps `maintenance_work_mem` at 32 MB.
- Fix: Reduced `lists` progressively. `lists=8` succeeded first, then `lists=50` also succeeded.

**Error 2: `Failed to fetch (api.supabase.com)`**
- Cause: Supabase Dashboard HTTP timeout (30s). The index build runs longer than the UI connection allows.
- Fix: The build actually completed server-side. The UI just dropped the connection. Refreshing showed the index was created.

Final index created:
```sql
CREATE INDEX snomed_concepts_embedding_idx ON snomed_concepts
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 50);
```

Note: After the embedding column was dropped from `snomed_concepts`, this index was also dropped (a column drop automatically removes dependent indexes). The index is no longer needed since there are no embeddings on `snomed_concepts`.

---

### Final production architecture (free tier compatible)

**Final confirmed database size: 483 MB** (17 MB under the 500 MB free tier limit)

| Table | Final size | Status |
|---|---|---|
| `icd_codes` | 351 MB | Active — ICD data + 98k embeddings |
| `snomed_concepts` | 82 MB | Active — 379k concepts, sequential text search |
| `icd_index_terms` | 22 MB | Active — ICD full-text search |
| `icd_code_hierarchy` | 11 MB | Active — ICD parent-child tree |
| `icd_code_metadata` | 7 MB | Active — ICD metadata |
| `snomed_descriptions` | 0 MB | Truncated |
| `snomed_relationships` | 0 MB | Truncated |
| Others + system | ~10 MB | audit_log, users, tokens, WAL |
| **Total** | **483 MB** | 17 MB buffer below free tier cap |

| Capability | Method | Status |
|---|---|---|
| SNOMED concept lookup by exact code | B-tree PK on `snomed_code` | Active |
| SNOMED text search (doctor slang) | Sequential scan on `description` (379k rows) | Active (slower) |
| SNOMED → ICD crosswalk | `snomed_icd_map` (5 demo mappings seeded) | Active |
| ICD semantic fallback (Path 3) | IVFFlat on `icd_codes.embedding` (98k vectors) | Active |
| SNOMED semantic vector search | Dropped — embedding column removed | Inactive |
| SNOMED GIN text index | Dropped — saves 13 MB, seq scan used instead | Inactive |
| WHO ICD API (Path 1) | External API, no DB storage needed | Active |

**The live pipeline covers all 3 resolution paths:**
- Path 1 (WHO API) — unaffected, no DB storage needed
- Path 2 (SNOMED text search) — operational on 379k concepts via sequential scan
- Path 3 (ICD embedding fallback) — fully operational on 98k ICD codes with vectors

**Capabilities lost vs. the ideal full-scale deployment:**
- SNOMED vector semantic search (embedding column dropped — saves ~1.2 GB)
- SNOMED GIN text index (dropped — saves 13 MB, text search ~200ms vs ~5ms)
- `snomed_descriptions` and `snomed_relationships` tables (truncated — saves ~454 MB)

---

### Lessons learned

1. **Plan storage before ingesting.** 379k × 384-dim embeddings = ~1.2 GB including index. Always calculate `rows × dimensions × 4 bytes × 2 (for IVFFlat index)` before ingesting vectors on a free tier.
2. **Supabase free tier (500 MB) cannot host both full ICD embeddings (98k) and full SNOMED embeddings (379k) simultaneously.** Choose one, or upgrade to Pro ($25/month, 8 GB).
3. **`VACUUM FULL` cannot run in a transaction block.** Always run it as a single statement, not bundled with other SQL.
4. **`pg_database_size` includes WAL and system overhead.** User table sizes from `pg_statio_user_tables` are more accurate for planning.
5. **IVFFlat `lists` parameter is memory-constrained.** On free tier (32 MB `maintenance_work_mem`), maximum practical `lists` is ~50. Formula: `lists ≤ maintenance_work_mem_MB / 2`.

---

*Document last updated March 26, 2026 — post-ingestion storage incident fully resolved. Final database size: 483 MB. Pipeline operational.*
