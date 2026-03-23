# 21 — Knowledge Reference: Seed Data, Agents, LangGraph & Test Cases

> **Purpose:** This is the deep-explainability document for Integronix.
> Use this during hackathon Q&A, architecture review, and future development.
> Written: 25-Feb-2026 | Status: COMPLETE (9/9 tests passing)

---

## PART 1 — Seed Data in the Database

### Why Do We Need Seed Data?

Integronix uses two medical knowledge bases: **ICD-10-CM codes** and **SNOMED-CT concepts**. These are not invented — they are real, standardized medical coding systems used globally. We seed a **representative subset** of the most clinically significant codes to demonstrate the full system capability without loading the entire 70,000+ code ICD-10-CM dataset.

---

### 1A. ICD-10 Codes Seeded (`icd_codes` table)

**Total seeded: 71 codes** (expanded over multiple migrations)

**Core initial seed (10 codes):**

| Code | Description | CC/MCC | DRG Base | Why It's In There |
|---|---|---|---|---|
| `E11.9` | Type 2 diabetes mellitus without complications | — | $1,200 | Baseline — most commonly miscoded. Undercoded when complications exist |
| `E11.22` | Type 2 DM with diabetic chronic kidney disease | CC | $2,100 | Key demo code. Shows $900 revenue uplift over E11.9 |
| `E11.40` | Type 2 DM with diabetic neuropathy, unspecified | CC | $1,900 | Secondary candidate in DM cases with nerve involvement |
| `N18.3` | Chronic kidney disease, stage 3 | CC | $1,500 | Co-diagnosis with DM. eGFR drives this staging |
| `N18.4` | Chronic kidney disease, stage 4 | CC | $1,750 | Advanced CKD — a more severe staging |
| `I10` | Essential (primary) hypertension | — | $900 | Most common chronic condition seen in US hospitals |
| `J18.9` | Pneumonia, unspecified organism | — | $1,800 | Common inpatient case, tests organism-unknown path |
| `J96.00` | Acute respiratory failure, unspecified | MCC | $3,500 | High-severity ICU case — MCC triggers DRG weight boost |
| `A41.9` | Sepsis, unspecified organism | MCC | $5,000 | Highest-revenue case. ICU + septic shock. Shows MCC impact |
| `I50.9` | Heart failure, unspecified | — | $2,400 | Cardiac failure — commonly associated with other conditions |

**Where is this data from?**
- ICD-10-CM official code set (CMS 2024 release: https://www.cms.gov/medicare/coding-billing/icd-10-codes)
- The `is_cc` and `is_mcc` flags follow official CMS DRG CC/MCC designation tables
- `base_reimbursement` values are **simulated** approximations of real DRG weights × national IPPS rates — for demonstration, not actual billing

---

### 1B. SNOMED-CT Concepts Seeded (`snomed_concepts` table)

**Total seeded: 17 concepts** (initially 5, expanded via migrations)

| SNOMED Code | Description | Semantic Tag | Why It's In There |
|---|---|---|---|
| `44054006` | Diabetes mellitus type 2 | (disorder) | Core concept — LLM extracts this for DM cases |
| `709044004` | Chronic kidney disease stage 3 | (disorder) | CKD staging — exact ICD match exists |
| `73211009` | Diabetes mellitus (generic) | (disorder) | Broader DM concept — catches ambiguous extractions |
| `59621000` | Essential hypertension | (disorder) | I10 maps exactly from this SNOMED code |
| `233604007` | Pneumonia | (disorder) | J18.9 maps from this |
| `79621000` | Chronic obstructive pulmonary disease | (disorder) | COPD coverage |
| `230690007` | Cerebrovascular accident (stroke) | (disorder) | High-MCC stroke cases |
| `22298006` | Myocardial infarction | (disorder) | Heart attack — surgical ICD mapping path |
| `84114007` | Heart failure | (disorder) | I50.9 maps from this |
| `301011002` | Septicemia | (disorder) | Sepsis-adjacent concept |
| `91302008` | Sepsis | (disorder) | A41.9 maps from this |
| `279639007` | Low back pain | (finding) | For embedding fallback test — no direct ICD mapping |
| `35489007` | Depressive disorder | (disorder) | For depression embedding fallback test |
| `66857006` | Neuropathy | (disorder) | E11.40 complication code trigger |
| `129721000` | Nephropathy | (disorder) | Kidney complication for DM cases |
| `95811000119104` | Acute respiratory failure | (disorder) | J96.00 high-severity mapping |
| `271737000` | Anaemia | (disorder) | Supplementary complication coverage |

**SNOMED source:** SNOMED International official release (https://www.snomed.org). SNOMED-CT-2024 July release. All SNOMED codes are real, active concepts.

---

### 1C. SNOMED → ICD Crosswalk (`snomed_icd_map` table)

**Total mappings: 11** (core clinically validated set)

| SNOMED | ICD | Type | Confidence | Why This Mapping |
|---|---|---|---|---|
| 44054006 (DM Type 2) | E11.22 | narrower | 0.91 | ICD is MORE specific — has CKD complication in code. Preferred when CKD documented |
| 44054006 (DM Type 2) | E11.9 | broader | 0.85 | ICD is LESS specific — use when no complications documented |
| 44054006 (DM Type 2) | E11.40 | narrower | 0.82 | ICD includes neuropathy — use when nerve complication mentioned |
| 709044004 (CKD stage 3) | N18.3 | exact | 0.99 | Perfect 1:1 semantic match |
| 59621000 (HTN) | I10 | exact | 0.99 | Perfect 1:1. Hypertension = I10 in ICD-10-CM |
| 233604007 (Pneumonia) | J18.9 | broader | 0.80 | ICD less specific (organism unknown) |
| 91302008 (Sepsis) | A41.9 | exact | 0.97 | Standard sepsis mapping |
| 84114007 (Heart failure) | I50.9 | exact | 0.95 | Heart failure exact mapping |
| 95811000119104 (Acute resp failure) | J96.00 | exact | 0.98 | Exact respiratory failure mapping |
| 35489007 (Depressive disorder) | F32.9 | exact | 0.96 | Major depressive disorder |
| 279639007 (Low back pain) | M54.5 | approximate | 0.66 | No direct mapping — falls to vector search |

**Mapping type definitions:**
- `exact` → Same clinical meaning. Highest trust. Node 4 uses directly.
- `narrower` → ICD code is MORE specific than SNOMED. Requires clinical evidence to justify.
- `broader` → ICD code is LESS specific. Trigger for specificity rules in Node 6.
- `approximate` → Related but not equivalent. Requires embedding similarity threshold > 0.60 to use.

---

## PART 2 — The 9 LangGraph Agents (Nodes)

Each "node" is a Python function decorated with `@safe_node()`. They share a single state object (`CodingState`) which flows through the entire graph.

---

### Node 1: `doc_processing_node` — Document Processing
**File:** `agents/doc_processor.py`

**What it does:**
- Accepts raw text OR base64-encoded PDF bytes
- If PDF: extracts text using `pdfplumber`
- Cleans text: strips headers/footers, normalizes whitespace
- Stores `raw_text` in state

**Why needed:** Clinical documentation comes in as messy PDF discharge summaries. Before any AI can read it, we need clean text. This is the data ingestion layer.

**Input state keys:** `raw_text` OR `pdf_bytes`
**Output state keys:** `raw_text` (cleaned)

---

### Node 2: `clinical_extract_node` — Clinical Extraction
**File:** `agents/clinical_extractor.py` → calls `services/extraction_service.py`

**What it does:**
- Sends raw text to **Groq API** (model: `llama-3.3-70b-versatile`)
- Instructs LLM to extract: diagnoses, severity levels, SNOMED candidate codes, LOINC observations
- Validates response with Pydantic schema
- Has retry logic (3 attempts with exponential backoff)

**Why this is the ONLY LLM node:**
> The LLM's job is **extraction** — reading English prose and turning it into structured JSON. It does NOT make coding decisions. It says "this patient has diabetes with CKD" — not "the code is E11.22". That is intentional.

**Input state keys:** `raw_text`
**Output state keys:** `structured_entities` (JSON: diagnoses[], observations[])

**Prompt structure:**
```
System: You are a clinical coding extraction agent...
User: Extract all diagnoses. For each: name, SNOMED code, severity, evidence text, LOINC labs.
Return valid JSON only.
```

---

### Node 3: `snomed_resolve_node` — SNOMED Resolver
**File:** `agents/snomed_resolver.py`

**What it does:**
- Takes LLM-extracted SNOMED candidates
- Validates they exist in our `snomed_concepts` table
- If exact match found → resolved
- If no match → fuzzy text search across all SNOMED descriptions
- Returns the confirmed SNOMED concept code

**Why needed:** LLM sometimes approximates SNOMED codes (hallucinates slightly). Node 3 grounds it against our actual validated SNOMED database. No unvalidated codes pass through.

**Input state keys:** `structured_entities`
**Output state keys:** `resolved_snomed_code`, `snomed_concept`

---

### Node 4: `snomed_icd_map_node` — SNOMED→ICD Mapper
**File:** `agents/snomed_icd_mapper.py`

**What it does:**
- Looks up resolved SNOMED code in `snomed_icd_map` table
- Returns all mapped ICD codes with their mapping types and confidence scores
- If mapping exists → sets `mapping_path = "direct"`
- If no mapping → sets `mapping_path = "embedding_fallback"` → triggers Node 5

**Why needed:** This is the crosswalk layer. SNOMED gives us clinical precision; `snomed_icd_map` gives us the billing code. This is how medical coding standards work in real hospitals (UMLS NLM crosswalk tables).

**Input state keys:** `resolved_snomed_code`
**Output state keys:** `candidate_icd_codes`, `mapping_path`

**Conditional routing logic:**
```
if mapping_path == "direct":    → go to Node 6 (icd_decision)
if mapping_path == "embedding_fallback": → go to Node 5 (icd_embedding)
```

---

### Node 5: `icd_embedding_node` — ICD Embedding Fallback
**File:** `agents/icd_embedding.py`

**What it does:**
- Only fires when Node 4 finds NO direct mapping
- Takes the clinical text description from structured entities
- Generates a 384-dim embedding using `all-MiniLM-L6-v2` (sentence-transformers)
- Queries Supabase `pgvector` index with cosine similarity search
- Returns top-K ICD codes with similarity scores
- Threshold: similarity > 0.60 to be included as a candidate

**Why needed (the "fallback" philosophy):**
> The real world has thousands of diagnoses. We can't manually curate a SNOMED→ICD mapping for every single one. Vector search solves the long tail problem. If Node 4 doesn't know what to do with "low back pain" or "major depressive disorder", Node 5 can find semantically similar ICD codes automatically.

**Input state keys:** `structured_entities`, `mapping_path = "embedding_fallback"`
**Output state keys:** `candidate_icd_codes` (populated from vector search)

---

### Node 6: `icd_decision_node` — Deterministic ICD Decision Engine
**File:** `agents/icd_decision.py`

**What it does (7-step algorithm):**
1. Build candidate pool from Node 4 or Node 5
2. Filter: only billable codes pass
3. Score specificity (code length + complication keywords + laterality)
4. Clinical consistency check (ICD desc words vs evidence text)
5. Combination code priority (prefer "with" codes per ICD-10 guidelines)
6. Weighted composite score: confidence(40%) + specificity(30%) + consistency(20%) + combination(10%)
7. Apply negation penalty (-0.4 if negation phrases found in text)
8. Select winner + build multi-code list (primary/secondary/additional)

**CRITICAL: This node uses ZERO AI/LLM. It is 100% deterministic rule-based.**

**Why deterministic?**
> ICD coding decisions affect hospital reimbursement — sometimes by $4,000+ per claim. You cannot let an LLM "guess" the code. It must follow the same ICD-10-CM Official Guidelines that human coders are trained to follow. A deterministic engine is auditable, reproducible, and defensible in a compliance review.

**Input state keys:** `candidate_icd_codes`, `structured_entities`, `raw_text`
**Output state keys:** `final_icd_code`, `confidence_score`, `icd_codes[]`

---

### Node 7: `audit_comparison_node` — Audit Comparison
**File:** `agents/audit_comparison.py`

**What it does:**
- Compares `final_icd_code` (AI decision) vs `human_icd_code` (what the coder entered)
- Computes financial delta (AI reimbursement - Human reimbursement)
- Classifies discrepancy type:
  - `EXACT_MATCH` — Human and AI agree
  - `SPECIFICITY_IMPROVEMENT` — AI found a more specific code (more revenue)
  - `OVERCODING` — Human code is too severe for the documentation
  - `UNSUPPORTED_CODE` — Human code doesn't exist in ICD-10-CM database
  - `NO_COMPARISON` — No human code was provided
- Detects DRG flags: `MCC_MISSED`, `CC_MISSED`, `MCC_OVERCODED`

**Why needed:** This is the "Revenue Integrity" layer. This is what hospital Revenue Cycle Management (RCM) departments do manually — Integronix automates it. Every $1 of revenue leakage detected here is the system's value proposition.

**Input state keys:** `final_icd_code`, `human_icd_code`, `icd_codes[]`
**Output state keys:** `discrepancy_type`, `financial_delta`, `drg_flag`

---

### Node 8: `risk_scoring_node` — Risk Scoring + DB Write
**File:** `agents/risk_scoring.py`

**What it does:**
- Computes risk score (0–100) based on:
  - Confidence score (lower confidence → higher risk)
  - Mapping path (embedding path → slightly higher risk than direct)
  - Discrepancy type (OVERCODING → big risk boost)
  - DRG flag severity (MCC_MISSED → risk boost)
- Labels: LOW (0–30), MEDIUM (31–60), HIGH (61–100)
- Writes complete result to `coding_results` table in Supabase
- Builds FHIR R4 `Condition` resource for interoperability output

**Why needed:** Provides an auditor-friendly risk signal. Hospital compliance teams use this to prioritize which claims to manually review before submission. High-risk claims = manual review. Low-risk = auto-submit.

**Input state keys:** everything from previous nodes
**Output state keys:** `risk_score`, `risk_label`, `fhir_condition` (written to DB)

---

## PART 3 — Why LangGraph? (and Why Not Plain LLM?)

### The Central Question

> "Can't you just send the clinical text to GPT-4 and ask it to return the ICD code?"

**Short answer: Yes, you CAN. But it would be wrong for a production medical coding system.** Here's why:

---

### What a Plain LLM Would Do

```python
response = openai.chat([
    {"role": "user", "content": f"What is the ICD-10 code for: {clinical_text}"}
])
code = response["choices"][0]["message"]["content"]
```

**Problems:**
| Problem | Real Impact |
|---|---|
| Hallucination | LLM makes up a code like "E11.23" that doesn't exist in 2024 ICD-10-CM |
| Non-determinism | Same input → different code on different runs |
| No audit trail | You can't explain WHY it chose E11.22 over E11.9 |
| No crosswalk | Skips SNOMED entirely — loses structured clinical ontology |
| No revenue awareness | Doesn't know E11.22 = $900 more than E11.9 |
| No specificity rules | Doesn't follow official ICD-10 "code to highest specificity" guideline |
| No negation detection | Would code E11.22 even when text says "no kidney disease" |

---

### Why LangGraph Solves This

LangGraph is a **stateful graph execution engine** for multi-step agent pipelines. It gives us:

#### 1. Separation of Concerns
Each node does ONE thing. LLM extraction (Node 2) is completely separate from ICD decision (Node 6). This means:
- The LLM can make mistakes in extraction → Node 3 validates it
- The deterministic engine makes the final code choice — not the LLM

#### 2. Stateful Flow
All 9 nodes share `CodingState`. Every node reads what previous nodes produced and adds its own output. This is impossible with a single LLM call.

#### 3. Conditional Routing
```python
graph.add_conditional_edges(
    "snomed_icd_map",
    route_by_mapping_path,
    {
        "direct":             "icd_decision",
        "embedding_fallback": "icd_embedding",
    }
)
```
A plain LLM call cannot branch. LangGraph routes to Node 5 automatically when Node 4 fails to find a mapping.

#### 4. Retry + Error Isolation
The `@safe_node` decorator wraps every node. If Node 3 crashes, it doesn't crash the whole pipeline — it marks the node as failed and continues. A plain LLM call crashes everything.

#### 5. Full Auditability
Every node's input and output is logged to the `audit_log` table. A compliance auditor can run one SQL query and see every single decision for any claim. This is a regulatory requirement in real healthcare IT.

#### 6. Deterministic Core
The most important business logic (ICD selection) is deterministic. LangGraph makes this explicit by separating the AI (Node 2) from the rule engine (Node 6).

---

### Architecture Comparison

| Feature | Plain LLM | Integronix (LangGraph) |
|---|---|---|
| ICD selection | Non-deterministic | 100% deterministic rule engine |
| Audit trail | None | Full 17-column audit_log per node |
| SNOMED ontology | Ignored | Full SNOMED→ICD crosswalk |
| Error handling | Full crash | Isolated per node |
| Revenue awareness | None | CC/MCC flags + DRG base values |
| Negation detection | Inconsistent | Explicit regex + evidence matching |
| Embedding fallback | None | pgvector cosine similarity |
| FHIR output | None | Full R4 Condition resource |
| Explainability | Black box | Every step logged with rationale |

---

## PART 4 — Test Cases: Full Explanation

### Test Suite Philosophy

The 9 test cases are designed to cover:
1. The **happy path** (the system works correctly)
2. **Edge cases** (tricky clinical scenarios)
3. **Adversarial inputs** (broken data, wrong codes, unsupported scenarios)
4. **Both mapping paths** (direct SNOMED→ICD and embedding fallback)

---

### TEST 1 — Happy Path: Diabetes + CKD
**Input text:** Patient with T2DM + CKD stage 3, eGFR 42, hypertension
**Human code entered:** E11.9

**What the system does:**
- Node 2 extracts: diagnosis=`Diabetes mellitus type 2 with CKD`, SNOMED=`44054006`
- Node 3 validates: `44054006` exists in snomed_concepts ✅
- Node 4 finds: 3 mappings (E11.22 narrower 0.91, E11.9 broader 0.85, E11.40 narrower 0.82)
- mapping_path = `direct`
- Node 6 scores: E11.22 wins (longer code = higher specificity, "with" keyword = combination bonus, "chronic kidney" in description = complication keyword bonus)
- Node 7: AI=E11.22 vs Human=E11.9 → SPECIFICITY_IMPROVEMENT, financial_delta = +$900
- Node 8: Risk=LOW (high confidence direct mapping)

**Why this test matters:** This is the primary demo case. It shows the core value proposition — catching $900 in revenue that a human coder left on the table by entering the non-specific E11.9.

**Result: ✅ PASS — E11.22, confidence 85%, LOW risk**

---

### TEST 2 — Embedding Fallback: Low Back Pain
**Input text:** Chronic low back pain, L4-L5 herniation
**Human code:** (none)

**What the system does:**
- Node 2 extracts: `Low back pain`, SNOMED=`279639007`
- Node 3 validates: found in snomed_concepts ✅
- Node 4: checks snomed_icd_map for `279639007` — **mapping type is `approximate`** (similarity 0.66)
- mapping_path = `embedding_fallback` (Node 5 fires)
- Node 5: generates embedding of "Low back pain" text → cosine search in icd_codes → returns M54.5 (66% sim), M54.51 (60% sim)
- Node 6 selects M54.5 — Low back pain

**Why this test matters:** Shows Node 5 (embedding fallback) works. This is critical because no hospital can pre-curate 70,000 ICD→SNOMED mappings. The pgvector fallback handles the long tail automatically.

**Result: ✅ PASS — M54.5 via EMBEDDING path, confidence 59%**

---

### TEST 3 — Negation Detection: No Complications
**Input text:** T2DM, no kidney disease, no neuropathy, well controlled on metformin
**Human code:** (none)

**What the system does:**
- Node 2 extracts: T2DM with no complications
- Node 4 returns candidates: E11.22, E11.9, E11.40
- Node 6 negation check: "no kidney disease" found in evidence → E11.22 gets -0.4 penalty → E11.22 score drops below E11.9
- E11.9 wins

**Why this test matters:** Shows negation detection. A naive system would code E11.22 whenever DM+CKD keywords appear together — even if the note says "NO kidney disease". Node 6's negation penalty prevents overcoding.

**Result: ✅ PASS — E11.9 selected (not E11.22)**

---

### TEST 4 — Ambiguous Documentation
**Input text:** T2DM diagnosed. Chart notes uncomplicated diabetes.
**Human code:** (none)

**What the system does:**
- Node 2: extracts basic T2DM, no complications noted
- Node 6: "uncomplicated" triggers negation → E11.9 wins over specific codes
- Low confidence (ambiguous documentation)

**Why this test matters:** Tests clinical conservatism. When documentation is ambiguous, the system defaults to the less specific code (E11.9). ICD-10 coding guidelines say "code from the documented findings" — if documentation is unclear, don't assume complications.

**Result: ✅ PASS — E11.9 selected conservatively**

---

### TEST 5 — Overcoding Detection
**Input text:** Essential hypertension, BP 160/100, no other comorbidities
**Human code entered:** A41.9 (Sepsis)

**What the system does:**
- Node 2: extracts Essential hypertension, SNOMED=`59621000`
- Node 4: finds exact mapping `59621000 → I10` (confidence 0.99)
- Node 6: I10 wins easily
- Node 7: AI=I10 ($900) vs Human=A41.9 ($5,000) → **OVERCODING**, financial_delta = -$4,100
- Node 8: Risk=MEDIUM (overcoding = compliance risk)

**Why this test matters:** This is the most dangerous error in medical coding. Submitting a sepsis code for a hypertension case is fraudulent billing. Integronix catches it and flags it before claim submission. In real hospitals, this kind of error leads to CMS audits, fines, and repayment demands.

**Result: ✅ PASS — I10, OVERCODING detected, -$4,100 delta**

---

### TEST 6 — Invalid Human Code (Guardrail)
**Input text:** ICU admission with sepsis and acute respiratory failure
**Human code entered:** XYZ999 (doesn't exist)

**What the system does:**
- Normal AI pipeline runs and selects A41.9 or J96.00
- Node 7: looks up human code `XYZ999` in icd_codes table → not found
- Sets discrepancy_type = `UNSUPPORTED_CODE`
- financial_delta = 0 (cannot compare against non-existent code)
- **System does NOT crash** — graceful handling

**Why this test matters:** In real EHR systems, coders sometimes enter typos, outdated codes, or nonexistent codes. The system must handle this gracefully — not crash — and flag it appropriately for human review.

**Result: ✅ PASS — No crash, UNSUPPORTED_CODE flagged correctly**

---

### TEST 7 — Multi-Diagnosis (Complex Patient)
**Input text:** T2DM + CKD stage 3 + hypertension + heart failure, eGFR 38, BNP elevated
**Human code:** E11.9

**What the system does:**
- Node 2: extracts FOUR separate diagnoses
- Node 4: returns multiple candidate pools for each SNOMED concept
- Node 6: merges and ranks across all candidates → E11.22 wins (DM+CKD combination highest value)
- Multi-code list: E11.22 (primary) + I10 (secondary) + I50.9 (additional)
- Combined DRG base value shown

**Why this test matters:** Real patients have multiple diagnoses. The system must handle "co-coding" — reporting all relevant diagnoses, not just the primary one. Multi-code output increases total claim reimbursement by capturing all billable comorbidities.

**Result: ✅ PASS — E11.22 primary, multi-code list shown, SPECIFICITY_IMPROVEMENT**

---

### TEST 8 — High Severity (MCC Case)
**Input text:** Septic shock, acute respiratory failure, mechanical ventilation, ICU admission
**Human code:** (none)

**What the system does:**
- Node 2: extracts sepsis + respiratory failure — BOTH are MCC-level conditions
- Node 4/5: A41.9 (sepsis) and J96.00 (resp failure) both returned
- Node 6: A41.9 wins (higher base DRG value, MCC flag)
- Node 8: Risk computed with MCC flag → MEDIUM risk
- MCC badge displayed in UI

**Why this test matters:** Shows the system can handle the highest-acuity cases. MCC (Major Complication/Comorbidity) classification is critical for DRG weight assignment — missing an MCC on an ICU case can cost a hospital $2,000–$5,000 per claim.

**Result: ✅ PASS — A41.9 with MCC badge, $5,000 DRG base**

---

### TEST 9 — Depression (Pure Embedding Path)
**Input text:** Major depressive disorder, single episode, low mood, anhedonia, sleep disturbance
**Human code:** (none)

**What the system does:**
- Node 2: extracts `Major depressive disorder`, SNOMED=`35489007`
- Node 3: validates `35489007` (Depressive disorder) ✅
- Node 4: finds mapping to F32.9 (if expanded mappings applied) OR full embedding fallback
- Node 5: generates embedding → matches `F32.9` in icd_codes via pgvector
- Node 6: F32.9 selected — Major depressive disorder, unspecified

**Why this test matters:** Mental health ICD codes are particularly prone to vague documentation. This test proves the semantic search layer handles conditions that have fewer direct SNOMED crosswalk entries. It's also different from all other tests (pure mental health case) which shows system breadth.

**Result: ✅ PASS — F32.9 via embedding, LOW risk**

---

## PART 5 — Test Results Summary (As Of 25-Feb-2026)

| Test | Input Scenario | Expected ICD | Actual ICD | Mapping | Confidence | Status |
|---|---|---|---|---|---|---|
| 1 | DM + CKD (happy path) | E11.22 | E11.22 | DIRECT | 85% | ✅ PASS |
| 2 | Low back pain (embedding) | M54.5 | M54.5 | EMBEDDING | 59% | ✅ PASS |
| 3 | DM, no complications | E11.9 | E11.9 | DIRECT | — | ✅ PASS |
| 4 | Ambiguous DM | E11.9 | E11.9 | DIRECT | — | ✅ PASS |
| 5 | HTN overcoded as sepsis | I10 | I10 | DIRECT | 66% | ✅ PASS |
| 6 | Invalid code XYZ999 | UNSUPPORTED | A41.9 + unsupported flag | — | — | ✅ PASS |
| 7 | Multi-diagnosis complex | E11.22 | E11.22 (multi-code) | DIRECT | 85% | ✅ PASS |
| 8 | Septic shock + ICU | A41.9 | A41.9 (MCC) | EMBEDDING | 50% | ✅ PASS |
| 9 | Major depressive disorder | F32.9 | F32.9 | EMBEDDING | — | ✅ PASS |

**Overall: 9/9 Tests Passing ✅**

---

## Quick Reference: Technology Roles

| Technology | Role in Integronix |
|---|---|
| **Groq (LLaMA 3.3-70b)** | Clinical text → structured JSON extraction ONLY |
| **LangGraph** | Orchestrates all 9 nodes with state + conditional routing |
| **FastAPI** | HTTP API layer exposing the LangGraph pipeline |
| **Supabase (PostgreSQL)** | Stores ICD codes, SNOMED concepts, results, audit logs |
| **pgvector** | Cosine similarity search for embedding fallback (Node 5) |
| **sentence-transformers (MiniLM)** | Generates 384-dim embeddings for semantic search |
| **Pydantic** | Validates all data at every boundary |
| **Next.js + Tailwind** | Frontend dashboard UI |
| **Recharts** | Candidate score bar chart |

---

*Document last updated: 25-Feb-2026*
*All 9 test cases verified against live system running on localhost:8000 + localhost:3000*
