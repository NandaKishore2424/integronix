# Integronix — AI Clinical Coding Engine
## Complete Project Documentation

> **Project:** Integronix  
> **Stack:** FastAPI · LangGraph · Groq (LLaMA 3.3-70B) · Supabase · pgvector · sentence-transformers  
> **Build period:** Feb 2026  
> **Purpose:** Hackathon project — intelligent ICD-10-CM coding engine that detects undercoding, overcoding, and revenue optimization opportunities in clinical documentation.

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Architecture Overview](#2-architecture-overview)
3. [Tech Stack Decisions](#3-tech-stack-decisions)
4. [Database Schema](#4-database-schema)
5. [LangGraph Pipeline — All 8 Nodes](#5-langgraph-pipeline--all-8-nodes)
6. [API Endpoints](#6-api-endpoints)
7. [Production Hardening](#7-production-hardening)
8. [Scoring Algorithm — Node 6](#8-scoring-algorithm--node-6)
9. [Migration History](#9-migration-history)
10. [Stress Test Results](#10-stress-test-results)
11. [Bugs Found and Fixed](#11-bugs-found-and-fixed)
12. [Current Project Status](#12-current-project-status)

---

## 1. Problem Statement

Medical billing coders manually assign ICD-10-CM codes to clinical diagnoses. Common errors:

| Error Type | Description | Financial Impact |
|---|---|---|
| **Undercoding** | Using E11.9 when E11.22 is clinically supported | Lost revenue (e.g. $900/case) |
| **Overcoding** | Billing A41.9 (Sepsis) for a hypertension case | Compliance risk, audit flags |
| **Unsupported codes** | Using deprecated or non-existent codes | Claim rejection |

Integronix automates ICD-10 code selection using a hybrid SNOMED→ICD mapping + semantic embedding pipeline, then audits the result against human coder input.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT (Frontend)                        │
│              Next.js · React · Tailwind                         │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTPS
┌──────────────────────────▼──────────────────────────────────────┐
│                      FASTAPI BACKEND                            │
│  /health  /api/v1/parse/run  /api/v1/code/run  /api/v1/icd/*  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              LANGGRAPH PIPELINE (8 Nodes)                │   │
│  │                                                          │   │
│  │  Node1       Node2        Node3        Node4             │   │
│  │  doc_proc → clinical → snomed  → snomed_icd              │   │
│  │             extract    resolve    mapper                  │   │
│  │                                     │                    │   │
│  │                              ┌──────▼──────┐             │   │
│  │                              │  mapping_   │             │   │
│  │                              │  path?      │             │   │
│  │                              └──┬──────┬───┘             │   │
│  │                            direct    no_mapping          │   │
│  │                              │          │                │   │
│  │                  ┌───────────┘      Node5                │   │
│  │                  │              icd_embedding            │   │
│  │                  │                  │                    │   │
│  │  Node6       Node7        Node8     │                    │   │
│  │  icd_dec ← ──────┘  → audit → risk_scoring              │   │
│  │  ision            comp    +DB write                      │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Services: pdf_service · extraction_service · logger           │
│  Database: database.py (Supabase REST client)                  │
└──────────────────────────┬──────────────────────────────────────┘
                           │ REST API (PostgREST)
┌──────────────────────────▼──────────────────────────────────────┐
│                        SUPABASE                                 │
│  Tables: icd_codes · snomed_concepts · snomed_icd_map           │
│          clinical_cases · coding_results · audit_log            │
│  Extensions: pgvector (384-dim embeddings)                      │
│  RPC: match_icd_codes() · match_snomed_concepts()               │
└─────────────────────────────────────────────────────────────────┘

External APIs:
  Groq API → llama-3.3-70b-versatile (Node 2)
  sentence-transformers/all-MiniLM-L6-v2 (Node 5, local)
```

---

## 3. Tech Stack Decisions

### Backend: FastAPI
- Async-native, perfect for LangGraph + Supabase REST
- Auto-generates OpenAPI/Swagger docs at `/docs`
- Pydantic v2 for strict schema validation throughout

### LLM: Groq (LLaMA 3.3-70B)
- Near-zero latency (~800ms for 600 tokens)
- Free tier viable for hackathon demo volume
- Used **only** for clinical text extraction (Node 2)
- No LLM involved in ICD selection — prevents hallucination

### Graph: LangGraph
- TypedDict state shared across all nodes
- `@safe_node` decorator wraps every node with error catching + latency logging
- Conditional routing after Node 4 (direct vs embedding path)

### Embeddings: sentence-transformers (local)
- `all-MiniLM-L6-v2` — 22MB, 384 dimensions
- Runs entirely locally, zero API cost
- pgvector cosine similarity in Supabase

### Database: Supabase
- PostgREST REST API (no ORM, full control)
- pgvector for semantic search
- Row-level security on production tables

---

## 4. Database Schema

### `icd_codes` (71 rows seeded)
```sql
code TEXT PRIMARY KEY          -- E11.22
description TEXT               -- "Type 2 diabetes mellitus with diabetic CKD"
chapter TEXT                   -- Endocrine, Circulatory, etc.
category TEXT                  -- Diabetes, CAD, etc.
is_billable BOOLEAN            -- Only billable codes pass Node 4/5
is_cc BOOLEAN                  -- Complication/Comorbidity flag
is_mcc BOOLEAN                 -- Major CC flag (higher reimbursement weight)
base_reimbursement NUMERIC     -- Simulated DRG value (e.g. 2100 for E11.22)
version TEXT                   -- ICD-10-CM-2024
embedding VECTOR(384)          -- semantic vector (generated by generate_embeddings.py)
```

### `snomed_concepts` (17 rows seeded)
```sql
snomed_code TEXT PRIMARY KEY   -- 44054006
description TEXT               -- "Diabetes mellitus type 2"
semantic_tag TEXT              -- (disorder)
hierarchy TEXT                 -- Clinical finding
embedding VECTOR(384)          -- for concept similarity search
is_active BOOLEAN
```

### `snomed_icd_map` (11 mappings)
```sql
snomed_code → references snomed_concepts
icd_code    → references icd_codes
mapping_type TEXT              -- exact | narrower | broader
confidence NUMERIC             -- 0.0–1.0
is_primary BOOLEAN             -- Primary recommended mapping
source TEXT                    -- manual | nhs_map
notes TEXT
```

### `clinical_cases`
```sql
session_id UUID
structured_entities JSONB      -- Full extracted entity tree
processing_status TEXT         -- COMPLETE | ERROR
completed_at TIMESTAMPTZ
```

### `coding_results`
```sql
session_id UUID → clinical_cases
resolved_snomed_code TEXT
mapping_path TEXT              -- direct | embedding | no_mapping
ai_icd_code TEXT
confidence_score NUMERIC
candidate_codes JSONB
human_icd_code TEXT
discrepancy_type TEXT          -- EXACT_MATCH | SPECIFICITY_IMPROVEMENT | etc.
evidence_text TEXT
financial_delta NUMERIC
risk_score NUMERIC
risk_label TEXT                -- LOW | MEDIUM | HIGH
audit_result_json JSONB
```

### `audit_log`
```sql
session_id UUID
node_name TEXT                 -- which LangGraph node wrote this
input_snapshot JSONB
output_snapshot JSONB
model_name TEXT
model_version TEXT
prompt_tokens INT
completion_tokens INT
total_tokens INT
latency_ms INT
icd_version TEXT
snomed_version TEXT
status TEXT                    -- success | error
error_detail TEXT
```

---

## 5. LangGraph Pipeline — All 8 Nodes

### Node 1 — `doc_processing` (`agents/doc_processor.py`)
- **Input:** `state["pdf_bytes"]` OR `state["raw_text"]` (pre-set via `/code/run`)
- **Output:** `state["raw_text"]`
- **Logic:** If `raw_text` already set → pass-through. Otherwise extract text from PDF using `pdfplumber`.
- **Key decision:** Pass-through mode allows API to bypass PDF extraction for raw text input.

---

### Node 2 — `clinical_extract` (`agents/clinical_extractor.py` + `services/extraction_service.py`)
- **Input:** `state["raw_text"]`
- **Output:** `state["structured_entities"]`, `state["extraction_metadata"]`
- **LLM:** Groq → `llama-3.3-70b-versatile`
- **Prompt:** Structured JSON extraction — diagnoses, SNOMED candidates, observations, evidence text
- **Schema enforced:** `ExtractionResult` (Pydantic) with `@field_validator` to convert string `"null"` → actual `None`
- **Retry logic:** Up to 3 attempts with exponential backoff
- **Logging:** `groq_call_success` with token counts and latency in every structured log line
- **Average:** 650 tokens, 850ms, ~3 diagnoses extracted

---

### Node 3 — `snomed_resolve` (`agents/snomed_resolver.py`)
- **Input:** `state["structured_entities"]["diagnoses"][0]["snomed_candidate"]`
- **Output:** `state["resolved_snomed_code"]`, `state["snomed_resolution_method"]`
- **Strategy 1:** Direct lookup by LLM-suggested SNOMED code in `snomed_concepts` table
- **Strategy 2:** 2-word sliding window text search on diagnosis entity text
  - e.g. "chronic low back pain" → tries pairs: "chronic low", "low back", "back pain" → matches "Low back pain" ✅
  - Stop words filtered before building pairs: `{patient, has, with, the, and, or, ...}`
- **Resolution methods:** `llm_suggested` | `text_matched` | `not_found`

---

### Node 4 — `snomed_icd_map` (`agents/snomed_icd_mapper.py`)
- **Input:** `state["resolved_snomed_code"]`
- **Output:** `state["candidate_icd_codes"]`, `state["mapping_path"]`, `state["direct_mapped_icd"]`
- **Logic:** Queries `snomed_icd_map` for all ICD codes mapped to the resolved SNOMED concept
- **Filter:** Only `is_billable = true` codes pass forward
- **Identifies primary:** `is_primary = true` in crosswalk entry
- **`mapping_path` values:** `"direct"` | `"no_mapping"` | `"no_snomed"`
- **Example:** SNOMED 44054006 → 3 candidates: E11.22 (primary), E11.9 (broader), E11.40 (narrower)

---

### Node 5 — `icd_embedding` (`agents/icd_embedding.py`)
**Triggered only when Node 4 returns `mapping_path = "no_mapping"`**

- **Input:** Primary diagnosis text from `state["structured_entities"]`
- **Embedding:** `all-MiniLM-L6-v2` → 384-dim vector (local, no API cost)
- **Query:** Supabase RPC `match_icd_codes(query_embedding, threshold=0.70, limit=5)`
- **3 Guardrails:**
  1. **Cosine similarity threshold** ≥ 0.70 — rejects weak matches
  2. **Chapter exclusion** — e.g. endocrine diagnoses can't match mental health codes
  3. **Billable-only filter** — non-billable codes excluded
- **Output:** same `candidate_icd_codes` structure as Node 4 (source=`"embedding"`)
- **Caches model** in module-level singleton (only downloads `all-MiniLM-L6-v2` once per server start)
- **Vector format fix:** PostgREST requires PG literal string `"[0.1, 0.2,...]"` — not a Python list. Converted via `_vector_to_pg_literal()` before every RPC call.

---

### Node 6 — `icd_decision` (`agents/icd_decision.py`)
**7-step deterministic algorithm. NEVER random. NEVER LLM.**

- **Input:** `candidate_icd_codes`, `structured_entities`, `raw_text`
- **Scoring formula:**
  ```
  final_score = confidence×0.40 + specificity×0.30 + consistency×0.20 + combination×0.10 + negation_penalty
  ```
- **Phase 5A — Multi-code output:** Returns `icd_codes` list with primary + secondary + additional roles
  ```json
  [
    { "code": "E11.22", "role": "primary",    "rationale": "CC; more specific than SNOMED" },
    { "code": "E11.40", "role": "secondary",  "rationale": "CC; comorbidity candidate" },
    { "code": "E11.9",  "role": "additional", "rationale": "broader SNOMED match" }
  ]
  ```
  Secondary/additional only appear when `final_score ≥ 0.40`.

| Component | Formula | Notes |
|---|---|---|
| **Confidence** (40%) | Crosswalk confidence value | 0.91 for primary mappings |
| **Specificity** (30%) | `len(code)×0.15` + complication keyword matches | E11.22 > E11.9 |
| **Consistency** (20%) | Fraction of ICD description words in evidence text | Grounds code in documentation |
| **Combination bonus** (10%) | +0.2 if code matches `\bwith\b` / `"complicated by"` | ICD-10 combination code preference |
| **Negation penalty** | -0.4 if negation phrase found in raw text | Prevents overcoding when "no complications" seen |

- **Negation phrases:** "no complications", "without complications", "no kidney disease", "no renal", "normal kidney function", etc.
- **Checked in:** both entity `evidence_text` AND original `raw_text` (LLM often omits negations from extracted fields)

---

### Node 7 — `audit_comparison` (`agents/audit_comparison.py`)
**Only runs if `human_icd_code` is provided in the request**

- **Input:** `state["final_icd_code"]`, `state["human_icd_code"]`
- **Looks up both codes** in `icd_codes` table for description + reimbursement
- **`financial_delta`** = AI reimbursement − Human reimbursement
- **Phase 5A — DRG gap detection:** Compares MCC/CC flags and sets `drg_flag`:

| `drg_flag` | Condition | DRG Impact |
|---|---|---|
| `MCC_MISSED` | AI=MCC, Human≠MCC | Highest — DRG weight shift |
| `CC_MISSED` | AI=CC, Human≠CC | Medium — DRG downgrade risk |
| `MCC_OVERCODED` | Human=MCC, AI≠MCC | Compliance risk |
| `null` | No gap | None |

`drg_flag` is appended to the `explanation` string and included in both `discrepancy` dict and top-level response.

| Discrepancy Type | Condition |
|---|---|
| `EXACT_MATCH` | AI code == Human code |
| `SPECIFICITY_IMPROVEMENT` | AI code longer (more specific) than human |
| `OVERCODING` | Human code more specific than clinical evidence supports |
| `UNSUPPORTED_CODE` | Human code not found in ICD-10-CM-2024 |
| `NO_COMPARISON` | No human code provided |

---

### Node 8 — `risk_scoring` (`agents/risk_scoring.py`)
- **Computes risk score** deterministically from:
  ```
  risk = (1-confidence)×0.4 + discrepancy_risk×0.4 + delta_boost×0.1 + mcc_boost×0.1
  ```
- **Phase 5A — DRG-aware MCC boost:**

| Condition | Boost |
|---|---|
| `drg_flag == MCC_MISSED` | +0.20 (highest scrutiny) |
| `drg_flag == CC_MISSED` or `MCC_OVERCODED` | +0.15 |
| AI code is MCC (no gap) | +0.10 |
| No MCC/CC | +0.00 |

- **Risk labels:** LOW (<0.35) | MEDIUM (0.35–0.70) | HIGH (>0.70)
- **DB writes (all non-blocking):** `clinical_cases` + `coding_results` + `audit_log` (now includes `icd_codes` and `drg_flag` in snapshot)

---

## 6. API Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness probe + Supabase connection check |
| `GET` | `/api/v1/icd/{code}` | Fetch single ICD code metadata |
| `GET` | `/api/v1/icd/snomed/{code}/mappings` | Get SNOMED→ICD mappings |
| `POST` | `/api/v1/parse/run` | Run Nodes 1-2 only (extraction only) |
| `POST` | `/api/v1/code/run` | **Full 8-node pipeline** |

### `POST /api/v1/code/run` — Request
```json
{
  "raw_text": "Patient has Type 2 diabetes mellitus with CKD stage 3...",
  "session_id": null,
  "human_icd_code": "E11.9"
}
```

### `POST /api/v1/code/run` — Response (Phase 5A)
```json
{
  "session_id": "be0b3821-...",
  "final_icd_code": "E11.22",
  "confidence_score": 0.8507,
  "mapping_path": "direct",
  "resolved_snomed_code": "44054006",
  "icd_codes": [
    { "code": "E11.22", "role": "primary",    "is_cc": true, "base_reimbursement": 2100, "rationale": "CC; more specific than SNOMED" },
    { "code": "E11.40", "role": "secondary",  "is_cc": true, "base_reimbursement": 1900, "rationale": "CC; comorbidity candidate" },
    { "code": "E11.9",  "role": "additional", "is_cc": false,"base_reimbursement": 1200, "rationale": "broader SNOMED match" }
  ],
  "discrepancy_type": "SPECIFICITY_IMPROVEMENT",
  "discrepancy": { "explanation": "... CC missed by human coder — potential DRG downgrade.", "revenue_delta": 900, "drg_flag": "CC_MISSED" },
  "financial_delta": 900,
  "drg_flag": "CC_MISSED",
  "risk_score": 0.1727,
  "risk_label": "LOW",
  "fhir_condition": { "resourceType": "Condition", "code": { "coding": [...] }, "clinicalStatus": {...} },
  "extraction_metadata": { "model": "llama-3.3-70b-versatile", ... },
  "error_at": null
}
```

---

## 7. Production Hardening

### Structured Logging (`logger.py`)
- Every log line is JSON: `{timestamp, level, module, message, ...extra_fields}`
- All LLM calls log: model, tokens (prompt/completion/total), latency_ms
- All node transitions log: node_name, session_id, latency_ms, status
- Custom `StructuredLogger` accepts any kwargs → avoids runtime errors on unknown keys

### `@safe_node` Decorator (`agents/node_runner.py`)
- Wraps every node: measures latency, logs start/complete/error
- On exception: sets `state["error_at"]` and `state["error_detail"]`, returns gracefully
- Pipeline continues even if a node fails (no crash)

### Exception Hierarchy (`exceptions.py`)
```
IntegronixError
├── PDFExtractionError
├── LLMExtractionError
├── DatabaseError
├── SnomedResolutionError
└── ICDMappingError
```

### Pydantic Validation (`models.py`)
- `@field_validator` on `SnomedCandidate.code` converts string `"null"` → actual `None`
- Same validator on `severity`, `laterality` fields
- `ConfigDict(protected_namespaces=())` on `ExtractionMetadata` suppresses `model_*` warning

### Configuration (`config.py`)
- All env vars typed and validated via Pydantic Settings
- `groq_model_version`, `icd_version`, `snomed_version` tracked on every call

---

## 8. Scoring Algorithm — Node 6

### Example: E11.22 vs E11.9 for "Diabetes + CKD stage 3"

| Metric | E11.22 | E11.9 |
|---|---|---|
| Mapping confidence | 0.91 (primary) | 0.85 (broader) |
| Specificity (code len 6) | 0.90 | 0.75 |
| Clinical consistency | 0.80 ("kidney" in evidence) | 0.50 |
| Combination bonus | +0.20 ("with" in description) | 0.00 |
| Negation penalty | 0.00 | 0.00 |
| **Final score** | **0.8507** ✅ | **0.745** |

### Updated Example: E11.9 wins for "Diabetes, no complications documented"

| Metric | E11.22 | E11.9 |
|---|---|---|
| Mapping confidence | 0.91 (primary) | 0.85 (broader) |
| Specificity | 0.90 | 0.75 |
| Clinical consistency | 0.30 (kidney not in evidence) | 0.55 |
| Combination bonus | +0.20 (`\bwith\b` matched) | 0.00 ("without" ≠ `\bwith\b`) |
| **Negation penalty** | **-0.40** ("no complications" in raw_text) | **0.00** |
| **Final score** | **0.2873** | **0.615** ✅ |

> **Key fix:** `\bwith\b` regex prevents `"without"` from triggering the combination bonus or complication detection on E11.9.

---

## 9. Migration History

| File | Description |
|---|---|
| `001_enable_extensions.sql` | Enable pgvector + uuid-ossp |
| `002_create_icd_codes.sql` | ICD codes table with VECTOR(384) |
| `003_create_snomed_tables.sql` | snomed_concepts + snomed_icd_map |
| `004_create_clinical_cases.sql` | clinical_cases table |
| `005_create_coding_results.sql` | coding_results with all scoring fields |
| `006_create_audit_log.sql` | audit_log for node-level tracing |
| `007_create_indexes.sql` | Performance indexes on all FK and filter columns |
| `008_seed_data.sql` | Initial 10 ICD codes + 5 SNOMED concepts + 6 mappings |
| `009_expanded_seed.sql` | 60+ ICD codes across 9 chapters + 12 SNOMED concepts |
| `010_vector_search_rpc.sql` | `match_icd_codes()` + `match_snomed_concepts()` pgvector RPC |

---

## 10. Stress Test Results — Final (All 9/9 Passing)

Full test matrix run against `POST /api/v1/code/run`:

| # | Category | Input Summary | Expected | Actual | Status |
|---|---|---|---|---|---|
| 1 | Happy path | Diabetes + CKD + E11.9 human | E11.22, SPECIFICITY, +$900 | E11.22, +$900, LOW | ✅ PASS |
| 2 | **Embedding fallback** | Back pain (no SNOMED→ICD map) | embedding path, M54.5 | M54.5, similarity 0.656, embedding | ✅ PASS |
| 3 | **Ambiguous, negated** | "Diabetes. No complications. No kidney disease." | E11.9 (not E11.22) | E11.9 wins (E11.22 penalized −0.40) | ✅ PASS |
| 4 | Conflicting docs | No CKD documented | E11.9 | E11.9, confidence 0.845 | ✅ PASS |
| 5 | Wrong human code | Hypertension + human A41.9 | OVERCODING, −$4100 | I10, OVERCODING, −$4100, MEDIUM | ✅ PASS |
| 6 | Invalid human code | XYZ999 entered | UNSUPPORTED_CODE, no crash | flagged, error_at=null | ✅ PASS |
| 7 | Multi-diagnosis | DM+CKD+HTN+CHF + E11.9 human | E11.22, +$900 | E11.22, +$900 | ✅ PASS |
| 8 | High severity / MCC | Sepsis + resp failure | Graceful UNKNOWN | UNKNOWN, MEDIUM, no crash | ✅ PASS |
| 9 | Depression path | Major depressive disorder | F32.9 via embedding | F32.9, similarity 0.813 | ✅ PASS |

**Supabase verification:** 10+ rows written to `coding_results` + `audit_log` confirming end-to-end DB write path.

---

## 11. Bugs Found and Fixed

| # | Bug | Root Cause | Fix |
|---|---|---|---|
| 1 | `500` on `/parse/run` | `StructuredLogger.process` rejected unknown kwargs like `model_version` | Updated to accept any kwargs as `extra_fields` |
| 2 | `"code": "null"` (string) | Groq returns text `"null"` for unknown SNOMED codes | `@field_validator` on `SnomedCandidate.code` |
| 3 | Pydantic `model_version` warning | `model_*` is a protected namespace | `ConfigDict(protected_namespaces=())` |
| 4 | `extract_clinical_entities` return unpack | Returns tuple `(result, metadata)` but route expected single value | Route fixed to unpack correctly |
| 5 | SNOMED resolved CKD for "low back pain" | `diagnosis_text.split()[0]` = `"chronic"` matched "**Chronic** kidney disease" | Replaced with 2-word sliding window pairs |
| 6 | E11.22 selected when "no complications" | Negation check only looked at entity `evidence_text`, LLM omits negations from extracted fields | Also checks `raw_text` from state |
| 7 | E11.9 got negation penalty too | `"with" in "without"` substring false positive — both codes penalized | Replaced with `\bwith\b` regex word boundary |
| 8 | Vector RPC returned 0 hits | PostgREST needs PG literal string `"[x,y,...]"` — Python list `[x,y,...]` silently fails cast | `_vector_to_pg_literal()` converter in Node 5 |
| 9 | Threshold too high (0.70) | "chronic low back pain" vs "Low back pain" cosine similarity ≈ 0.65 | Lowered to 0.55 |

---

## 12. Current Project Status

### ✅ Phase 1–4 + Phase 5A — Backend Complete (All 9/9 Tests Passing)
- FastAPI backend on port 8000, all 8 nodes wired and tested
- Supabase connected, 6 tables seeded
- Structured JSON logging, `@safe_node` error handling, exception hierarchy
- Node 5 embedding fallback (threshold=0.55, chapter exclusion, vector format fix)
- Node 6 **multi-code output** — primary/secondary/additional with rationale and score
- Node 7 **DRG-aware gap detection** — `drg_flag` (MCC_MISSED / CC_MISSED / MCC_OVERCODED)
- Node 8 **DRG-weighted risk boost** — MCC_MISSED adds +0.20 to risk score
- **FHIR R4 Condition** included in every API response
- All 9/9 stress tests passing including embedding fallback + negation detection

---

## 13. Frontend — Phase 5B

### Tech Stack
- **Next.js 14** (App Router, TypeScript)
- **Tailwind CSS 3** (custom design tokens)
- **Recharts** (candidate score bar chart)
- **Lucide React** (icons)
- No shadcn dependency — all components written from scratch

### Design System
- Background: `#0d1117` with purple + cyan radial glow gradients
- Cards: glassmorphism — `rgba(255,255,255,0.08)` + `backdrop-filter: blur(24px)`
- Primary accent: `#6366f1 → #8b5cf6` gradient
- Hero heading: gradient text (indigo → purple → sky)
- Button: gradient with glow shadow, hover lift
- Typography: Inter (body) + JetBrains Mono (code/labels)

### Page Layout (Two Tabs)
**Tab 1 — Code Analysis:**
- Large textarea for clinical notes (monospace, dark, focus ring)
- Optional human ICD-10 code input for audit comparison
- 3 pre-loaded sample cases (Diabetes+CKD, Low Back Pain, DM No Complications)
- Pipeline visualisation sidebar (7 steps with descriptions)
- Animated pipeline stage label while loading

**Tab 2 — Results:**
- **Top strip:** session ID, mapping path, SNOMED code, revenue impact, re-analyse button
- **IcdCodeCard:** Primary code (large font), confidence bar, CC/MCC chips, SNOMED chain, DRG badge
- **RiskMeter:** SVG circular gauge, LOW/MEDIUM/HIGH colour-coded, risk + confidence stats
- **MultiCodeList:** Primary/secondary/additional code rows with role icon, score bar, rationale
- **CandidateChart:** Recharts horizontal bar chart, winner highlighted in bright indigo
- **AuditCard:** AI vs Human side-by-side, discrepancy badge, revenue delta (large), DRG alert
- **FhirPanel:** Collapsible, FHIR coding table + raw JSON + copy button
- **Metadata strip:** Model, ICD version, SNOMED version, LLM attempt

### Components
| File | Purpose |
|---|---|
| `app/page.tsx` | Main page — two-tab shell, pipeline submit handler |
| `app/layout.tsx` | Root layout — Inter font, metadata |
| `app/globals.css` | Full design system — glass cards, buttons, bars, tokens |
| `components/CodeInputPanel.tsx` | Input form with sample cases sidebar |
| `components/ResultsPanel.tsx` | Results grid orchestrator |
| `components/IcdCodeCard.tsx` | Primary AI code display |
| `components/MultiCodeList.tsx` | Primary/secondary/additional code hierarchy |
| `components/AuditCard.tsx` | Human vs AI comparison with revenue delta |
| `components/DrgBadge.tsx` | MCC/CC gap alert with pulsing dot |
| `components/CandidateChart.tsx` | Recharts bar chart of scored candidates |
| `components/RiskMeter.tsx` | SVG circular risk gauge |
| `components/FhirPanel.tsx` | Collapsible FHIR R4 JSON panel |
| `lib/api.ts` | Typed fetch wrapper for `/api/v1/code/run` |
| `types/coding.ts` | Full TypeScript interfaces for backend response |

---

## Scripts

```bash
# Start backend
cd backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000

# Start frontend
cd frontend
npm run dev    # → http://localhost:3001

# Generate embeddings (run once after seeding)
python3 scripts/generate_embeddings.py

# Run migrations (in Supabase SQL Editor, in order 001→010)
```

---

*Last updated: 2026-02-24 | Build: Phase 5A+5B Complete*
