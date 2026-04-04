# Integronix Database Schema Explained Simply

> **Who is this for?** Stakeholders, product managers, or engineers new to the project who need a high-level conceptual understanding of how data is organized before diving into raw SQL.
> This document explains the core tables, their purpose, and how they connect using simple analogies.

---

## 🏥 Think of the Database Like a Hospital Filing System

To manage complex medical data securely across many clients, we organize our database logically. Imagine a real hospital network:
- **Filing cabinets** are our **database tables**.
- **Folders inside the cabinets** are **rows (records)**.
- **Cross-references between folders** are **Foreign Keys (relationships)**.

We group our tables into three main categories: Tenants (Who), Medical Reference (The Rules), and Clinical Operations (The Work).

---

## Part 1: The Multi-Tenant Hierarchy (Who)

Integronix is a **multi-tenant** SaaS platform. This means many different hospitals use the same database, but they are strictly isolated from each other. Think of it like a secure apartment building: everyone shares the plumbing, but no one has the key to your apartment.

### The 3-Level Hierarchy

1.  **`organizations` (The Hospital Group)**: This is the top level. e.g., "Apollo Hospitals". Every piece of data rolls up to a specific organization.
2.  **`branches` (The Physical Location/Wing)**: Organizations are divided into branches. e.g., "Apollo Greams Road - Cardiology". This allows for granular reporting.
3.  **`users` (The People)**: The actual doctors, coders, and admins who log in. Every user is linked to an organization, and usually a specific branch.

**Security Rule:** PostgreSQL Row-Level Security (RLS) acts as a bouncer. When a user queries a table, the bouncer quietly adds "WHERE organization_id = [YOUR_ORG]" to every request.

---

## Part 2: The Medical Reference Tables (The Rules)

These tables are like massive, fixed **medical dictionaries**. They contain the universal rules of medical coding. They don't change daily, only when official updates are released (e.g., yearly by the CDC or WHO).

### 1. `icd_codes` (The Master Dictionary)
The official list of disease billing codes.
*   *Example row:* Code: `E11.9`, Description: "Type 2 diabetes mellitus without complications", is_billable: `True`.
*   *Hidden Power:* This table also holds the **Vector Embeddings**—the mathematical representations of the text that allow our AI to do "fuzzy" searches instead of exact keyword matches.

### 2. `icd_code_hierarchy` & `icd_code_metadata` (The Rules of the Dictionary)
ICD codes aren't just a flat list; they are a tree.
*   `hierarchy`: Tells us that `E11.9` is a child of `E11` (Type 2 diabetes).
*   `metadata`: Holds strict rules. For example, it might say "Code First: underlying condition" or "Excludes1: Type 1 diabetes (E10)".

### 3. `snomed_concepts` & `snomed_icd_map` (The Translator)
Doctors often write in clinical terms, not billing codes. SNOMED-CT is a global standard for clinical terms.
*   `snomed_concepts`: A list of clinical concepts.
*   `snomed_icd_map`: A crucial translation table mapping a clinical SNOMED concept to its corresponding financial ICD-10 code.

---

## Part 3: Clinical Operations Tables (The Work)

This is where the daily action happens. These tables grow rapidly as users upload documents and the AI processes them.

### 1. `clinical_cases` (The Patient Chart)
Every time a user uploads a PDF or pastes text, a new "case" is created.
*   **Holds:** The raw clinical text, the date, and who uploaded it.
*   **Security:** Firmly stamped with `organization_id` and `branch_id`.

### 2. `coding_results` (The AI's Answer)
Once the pipeline finishes processing a case, the result is saved here.
*   **Holds:** The `final_icd_code` selected by the system, the AI's `confidence_score`, and the structured FHIR JSON representation of the clinical evidence.
*   **Link:** Tied directly to a `clinical_case_id`.

### 3. `org_settings` (The Hospital's Preferences)
Different hospitals code differently. This table stores those preferences.
*   **Configuration:** Tells the pipeline whether to use `ICD-10` or `ICD-11`, and if they are operating under a specific `claim_scheme` (like Ayushman Bharat). This table drives the conditional routing in our agent pipeline.

### 4. `audit_log` (The Security Camera)
A chronological record of every significant action taken in the system by users (e.g., logging in, changing a setting, confirming a code). Essential for HIPAA compliance.

---

**Summary:** The database is designed so that *Users* in *Organizations* process *Cases* to get *Results*, using a fixed set of *Medical Rules*, with everything governed by *Org Settings* and recorded in the *Audit Log*.

| `code` | The ICD code itself (e.g. "E11.22") |
| `description` | What disease this code means |
| `is_cc` | Is this a Complication? (affects hospital payment) |
| `is_mcc` | Is this a Major Complication? (bigger payment impact) |
| `embedding` | A mathematical "fingerprint" of the description (used for search) |

**Real-world analogy:** Think of ICD codes like product barcodes at a supermarket. Every disease has a barcode. The hospital submits these barcodes to insurance for payment.

---

### `snomed_concepts` table
SNOMED is a **clinical language** — how doctors actually write and talk about diseases.
ICD is the **billing language** — what insurance companies understand.

Integronix translates between the two.

| Column | What it means |
|---|---|
| `snomed_code` | Doctor's language code (e.g. 73211009) |
| `preferred_term` | "Diabetes mellitus type 2" |
| `embedding` | Mathematical fingerprint for AI search |

**Simple analogy:** If a doctor writes "sugar disease", SNOMED understands it means "Type 2 Diabetes Mellitus", and ICD translates that to "E11.9" for the insurance claim.

---

### `snomed_icd_map` table
The **bridge** between doctor language and billing language.

```
SNOMED 73211009 (Diabetes mellitus type 2)  →  ICD E11.9
SNOMED 59621000 (Essential hypertension)    →  ICD I10
```

---

## Part 3: The Operational Tables (Migrations 004–006, updated in 014)

These tables **grow every day** as the hospital uses the system.

### `clinical_cases` table
One row = **one patient document** submitted for coding review.

| Column | What it means |
|---|---|
| `organization_id` 🆕 | Which hospital submitted this? |
| `branch_id` 🆕 | Which branch? |
| `submitted_by` 🆕 | Which coder (user) submitted it? |
| `raw_text` | The actual doctor's notes (could be messy!) |
| `document_source` 🆕 | Was it typed text, a PDF, or from an EHR system? |
| `ocr_used` 🆕 | Did we use OCR to read a scanned/handwritten document? |
| `processing_status` | PENDING → PROCESSING → COMPLETE / FAILED |
| `structured_entities` | After AI reads the notes, what diseases were found? |

**Real-world analogy:** A coder scans a doctor's discharge summary and drops it in the Integronix inbox. This table is that inbox.

---

### `coding_results` table
One row = **the AI's answer** for a submitted case.

| Column | What it means |
|---|---|
| `organization_id` 🆕 | Which hospital this result belongs to |
| `case_id` | Links back to the case that was analysed |
| `ai_icd_code` | What ICD code the AI recommends |
| `confidence_score` | How sure is the AI? (0.0 to 1.0) |
| `human_icd_code` | What code the human coder entered |
| `discrepancy_type` | Do the AI and human agree? If not, why? |
| `financial_delta` | If AI is right, how much $ is the hospital losing/overclaiming? |
| `risk_score` | How likely is this claim to be audited by insurance? |
| `claim_json` | FHIR-format output for EHR systems |

**Real-world analogy:** This is the AI's report card for each case. It says "Human said E11.9, but actually it should be E11.22, and this mistake costs the hospital $2,300."

---

### `audit_log` table
Every step the AI pipeline takes is **recorded here**. This is the explainability layer.

| Column | What it means |
|---|---|
| `session_id` | Which case is this log for? |
| `node_name` | Which AI step logged this? (e.g. "clinical_extract") |
| `input_snapshot` | What data went INTO this step? |
| `output_snapshot` | What came OUT of this step? |
| `latency_ms` | How long did this step take? |
| `status` | Did it succeed, use a fallback, or fail? |

**Real-world analogy:** Like a flight recorder (black box) — every decision the AI made is logged so it can be reviewed.

---

### `revenue_lookup` table
A reference table: **how much does each ICD code pay?**

```
E11.22 + MCC → $8,200 base reimbursement
I10           → $4,100 base reimbursement
A41.9 + MCC  → $13,000 base reimbursement
```

---

## Part 4: The Complete ER Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    MULTI-TENANT LAYER                           │
│                                                                 │
│  ┌──────────────────┐                                          │
│  │  organizations   │                                          │
│  │──────────────────│                                          │
│  │ id (PK)         │                                          │
│  │ name            │                                          │
│  │ type            │                                          │
│  └────────┬─────────┘                                          │
│           │ 1                                                   │
│           │ has many                                            │
│           ▼ N                                                   │
│  ┌──────────────────┐     ┌──────────────────┐                 │
│  │    branches      │     │      users        │                 │
│  │──────────────────│     │──────────────────│                 │
│  │ id (PK)         │     │ id (PK)          │                 │
│  │ organization_id ├────►│ organization_id  │                 │
│  │ name            │  ┌─►│ branch_id        │                 │
│  └────────┬─────────┘  │  │ role             │                 │
│           │ 1          │  └──────────────────┘                 │
│           └────────────┘                                        │
└─────────────────────────────────────────────────────────────────┘
                           │ (org_id + branch_id flow down)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CLINICAL WORKFLOW                            │
│                                                                 │
│  ┌──────────────────┐                                          │
│  │ clinical_cases   │  ← Doctor note / PDF dropped here       │
│  │──────────────────│                                          │
│  │ case_id (PK)    │                                          │
│  │ organization_id │                                          │
│  │ branch_id       │                                          │
│  │ submitted_by    │                                          │
│  │ raw_text        │                                          │
│  │ ocr_used        │                                          │
│  └────────┬─────────┘                                          │
│           │ 1                                                   │
│           │ produces                                            │
│           ▼ 1                                                   │
│  ┌──────────────────┐                                          │
│  │ coding_results   │  ← AI's answer + revenue impact         │
│  │──────────────────│                                          │
│  │ result_id (PK)  │                                          │
│  │ case_id (FK)    │                                          │
│  │ organization_id │                                          │
│  │ ai_icd_code     │──────────────────────────────┐           │
│  │ human_icd_code  │                              │           │
│  │ financial_delta │                              ▼           │
│  └─────────────────┘              ┌──────────────────────┐    │
│                                   │     icd_codes        │    │
│  ┌──────────────────┐             │──────────────────────│    │
│  │   audit_log      │             │ code (PK)            │    │
│  │──────────────────│             │ description          │    │
│  │ session_id       │◄──────────  │ is_cc / is_mcc       │    │
│  │ node_name        │  traces     │ embedding            │    │
│  │ input_snapshot   │  every step └──────────┬───────────┘    │
│  │ output_snapshot  │                        │ mapped via      │
│  └──────────────────┘                        ▼                 │
│                                   ┌──────────────────────┐    │
│                                   │  snomed_icd_map      │    │
│                                   │──────────────────────│    │
│                                   │ snomed_code (FK)     │    │
│                                   │ icd_code (FK)        │    │
│                                   └──────────┬───────────┘    │
│                                              │                 │
│                                              ▼                 │
│                                   ┌──────────────────────┐    │
│                                   │  snomed_concepts     │    │
│                                   │──────────────────────│    │
│                                   │ snomed_code (PK)     │    │
│                                   │ preferred_term       │    │
│                                   └──────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Part 5: How Data Flows — A Real Story

> **Scenario:** Maria Santos (coder at Cardiology branch) uploads a discharge summary.

```
1. Maria logs in
   → System checks: org = City General Hospital, branch = Cardiology, role = coder
   → RLS policy activates: she can only see Cardiology's cases

2. She pastes a messy doctor note:
   "pt has t2dm w/ ckd stg3, bp ok on lisinopril"
   → clinical_cases row created
      organization_id = City General Hospital ✓
      branch_id       = Cardiology ✓
      submitted_by    = Maria Santos ✓
      ocr_used        = FALSE (it was typed directly)

3. AI pipeline processes it (8 steps, each logged to audit_log)
   Step 1: Cleans and reads the text
   Step 2: LLM extracts → "Type 2 diabetes + CKD stage 3"
   Step 3: Finds SNOMED concept 73211009
   Step 4: Maps to ICD E11.22 (direct crosswalk)
   Step 6: Deterministic engine confirms E11.22 (not E11.9)
   Step 7: Compares to human's E11.9 → SPECIFICITY_IMPROVEMENT
   Step 8: Revenue delta = +$2,100

4. Result saved to coding_results
   → organization_id = City General Hospital ✓  (RLS protected)
   → ai_icd_code     = E11.22
   → financial_delta = +$2,100

5. Sarah (admin) logs in
   → She sees ALL branches' results
   → She spots Cardiology consistently undercoding DM cases
   → She schedules a training for that team
```

---

## Part 6: Why RLS (Row-Level Security) Matters

Imagine two hospitals use Integronix:

```
Hospital A: City General Hospital (org_id = AAA)
Hospital B: Metro Health System  (org_id = BBB)
```

Without RLS, if Hospital B's coder somehow got Hospital A's login token,
they could run a query and see Hospital A's patients.

**With RLS enabled:**
```sql
SELECT * FROM clinical_cases;
-- Returns ONLY rows where organization_id = your own org
-- Hospital B never sees Hospital A's data
-- Even if the query is correct, the DB itself blocks it
```

This is enforced **inside the database**, not in Python code. It's the safest possible data isolation.

---

## Part 7: Summary Table — All 14 Tables

| Table | Category | Purpose |
|---|---|---|
| `organizations` | 🆕 Multi-tenant | Top-level tenant entity |
| `branches` | 🆕 Multi-tenant | Physical sub-units of an org |
| `users` | 🆕 Multi-tenant | People with roles and branch access |
| `icd_codes` | Reference | Medical billing codes dictionary |
| `snomed_concepts` | Reference | Clinical language terminology |
| `snomed_icd_map` | Reference | Bridge: clinical → billing language |
| `revenue_lookup` | Reference | DRG reimbursement amounts per code |
| `clinical_cases` | Operational | Patient documents submitted for review |
| `coding_results` | Operational | AI's code recommendation + audit |
| `audit_log` | Operational | Full pipeline trace (explainability) |

---

## Part 8: The "Bad Writing" Problem — How We Handle It

Doctors don't write perfectly. Here's how Integronix handles it:

| Problem | Example | Our Solution |
|---|---|---|
| Abbreviations | "t2dm", "dm2", "T2DM" | SNOMED sliding window catches all variants |
| Missing details | "patient has diabetes" | Conservative code (E11.9) selected, flag raised |
| Structured template | Copy/paste boilerplate with wrong values | LLM extracts only clinically mentioned conditions |
| Negation | "no signs of kidney disease" | Negation detection removes ICD codes for denied conditions |
| Scanned PDF | Handwritten notes photographed | OCR (Tesseract) converts image to text before AI reads it |
| Embedding fallback | Condition not in SNOMED map | pgvector similarity search finds closest match |

The `ocr_used` column in `clinical_cases` tells you if OCR was needed — useful for quality analytics.
