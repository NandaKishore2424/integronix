# ICD-10 Integration + Node Updates (March 2026)

This document summarizes the ICD-10-CM integration work and the recent LangGraph node updates, including inputs/outputs, routing logic, and quality considerations.

---

## 1) ICD-10-CM Integration (Data + Pipeline)

### 1.1 Data Sources
- **Order File (TXT):** Full ICD-10-CM code list and descriptions.
- **Tabular XML:** Official hierarchy + coding rules.
- **Index XML:** Search terms, synonyms, and redirects.

### 1.2 Database Tables Used
- **icd_codes** — Master code list (description, cc/mcc, embedding, billable).
- **icd_code_hierarchy** — Parent/child relationships from Tabular XML.
- **icd_code_metadata** — Includes/excludes, code-first, notes.
- **icd_index_terms** — Search terms for fast ICD lookups.

### 1.3 Parsing & Loading
**Modules**
- `backend/services/icd_parsers.py`
- `backend/services/icd_loader_service.py`
- `backend/services/icd_ingestion_service.py`

**Key Decisions**
- **Billable flag computed from hierarchy** (leaf nodes billable).
- **Index terms allow partial codes** (FK removed on index codes).
- **Invalid index codes filtered** (e.g., `I63.-`).

### 1.4 Ingestion Outputs
- **icd_codes:** 98,186
- **icd_code_hierarchy:** 46,881
- **icd_code_metadata:** 46,881
- **icd_index_terms:** 70,385
- **Invalid index codes filtered:** 6,955

---

## 2) Routing & Provider Layer (ICD-10 vs ICD-11)

### 2.1 Org Settings → Routing
`org_settings` determines the routing:
- `icd_version` (ICD-10 vs ICD-11)
- `claim_scheme`
- `coding_mode`

### 2.2 Provider Abstraction
The **ICD provider** chooses the correct data source:
- **ICD-10** → internal DB + index terms + embeddings
- **ICD-11** → WHO ICD API (MMS / Foundation)

This provider layer is used both by:
- `/icd/search` route (explicit search)
- Phase 3 fallback candidate augmentation inside the pipeline

---

## 3) LangGraph Node Updates (Phases 1–3)

### Phase 1 — Org Settings Injection
**What changed**
- `CodingState` now carries `icd_version`, `claim_scheme`, `coding_mode`.
- `/code/run` and `/code/run-pdf` inject org settings at the start.

**Why**
Ensures downstream nodes consistently route to ICD-10 or ICD-11.

---

### Phase 2 — WHO API Routing Guard
**What changed**
- `snomed_resolver` only calls WHO ICD API if `icd_version = ICD-11`.
- Otherwise it skips WHO and uses SNOMED/ICD-10 flows.

**Why**
Prevents unnecessary WHO calls and enforces policy routing.

---

### Phase 3 — Candidate Augmentation + Decision Trace
**What changed**
- If candidates are missing or too few, the provider is called to **augment**.
- Candidates are merged and deduped before decision scoring.
- `decision_trace` is added to the response for auditability.

**Why**
Improves coverage when direct mapping or embedding yields too few options.

---

## 4) Node-by-Node Inputs/Outputs (Current)

### Node 1 — Document Processing
**Input:** PDF bytes or raw text
**Output:** `raw_text`
**Deterministic**

### Node 2 — Clinical Extraction (LLM)
**Input:** `raw_text`
**Output:** `structured_entities`, `extraction_metadata`
**LLM** (Groq)

### Node 3 — SNOMED / WHO Resolver
**Input:** `structured_entities`, `icd_version`
**Output:** `resolved_snomed_code`, `candidate_icd_codes` (ICD-11 when WHO is used)
**Deterministic + external API**

### Node 4 — SNOMED → ICD Map
**Input:** `resolved_snomed_code`
**Output:** `candidate_icd_codes`
**Deterministic**

### Node 5 — Embedding Fallback
**Input:** `structured_entities`
**Output:** `candidate_icd_codes`
**Deterministic**

### Node 6 — ICD Decision
**Input:** `candidate_icd_codes`, `structured_entities`
**Output:** `final_icd_code`, `confidence_score`, `icd_codes` (multi-code)
**Deterministic**

### Node 7 — Audit Comparison (Conditional)
**Input:** `final_icd_code`, `human_icd_code`
**Output:** `discrepancy_type`, `discrepancy`, `financial_delta`
**Deterministic**

### Node 8 — Risk Scoring + FHIR
**Input:** `final_icd_code`, `discrepancy`
**Output:** `risk_score`, `risk_label`, `fhir_condition`, DB write
**Deterministic**

---

## 5) Candidate Definition
A **candidate** is a potential ICD code with metadata used for ranking:
- `code`, `description`, `icd_version`
- `mapping_type` (exact / narrower / broader / approximate)
- `confidence` / `similarity_score`
- `is_cc` / `is_mcc`, `base_reimbursement`

Candidates can be produced by:
- WHO ICD API
- SNOMED crosswalk
- Embedding similarity search
- Provider fallback (Phase 3)

---

## 6) Accuracy & Confidence (Important Clarification)

**Accuracy** is not explicitly measured in code; instead we expose **confidence** based on deterministic scoring + mapping quality. Key points:
- The system **does not output a code unless it exists in the DB**.
- **Confidence score** reflects ranking strength, not clinical ground‑truth accuracy.
- For production, accuracy must be validated with labeled datasets and QA audits.

---

## 7) Current Outputs Added
- **decision_trace** on API response
- **mapping_path** indicates which pipeline path was used
- **icd_codes** list includes primary/secondary/additional codes

---

## 8) Files Added/Updated (Summary)
- ICD ingestion + parsers + loaders (services + scripts)
- Routing provider (ICD-10 vs ICD-11)
- Updated LangGraph state and nodes
- Decision trace in responses

---

If you want this split into separate docs per node, or want diagrams, say the word and I’ll generate them.