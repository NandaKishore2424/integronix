# 22 — Integronix Database Explained Simply
> **Who is this for?** Someone who doesn't work with databases daily.
> This document explains every table, why it exists, and how they connect — with diagrams.

---

## 🏥 Think of the Database Like a Hospital Filing System

Imagine a real hospital. They have:
- **Filing cabinets** → our database tables
- **Folders in each cabinet** → rows (records)
- **Links between folders** → foreign keys (connections between tables)

Integronix has **14 tables** total. We'll go from simple to complex.

---

## Part 1: The Multi-Tenant Hierarchy (NEW — Migrations 011–013)

> **Multi-tenant** just means: "many organizations sharing one system, but each seeing only their own data."
> Think of it like Outlook — millions of companies use it, but no company sees another's emails.

### The 3-Level Hierarchy

```
🏢 ORGANIZATION  (e.g. "City General Hospital")
    │
    ├── 🏬 BRANCH  (e.g. "Cardiology Wing")
    │       │
    │       └── 👤 USER  (e.g. "Maria Santos — Coder")
    │
    └── 🏬 BRANCH  (e.g. "Endocrinology Wing")
            │
            └── 👤 USER  (e.g. "Raj Kumar — Coder")
```

### `organizations` table
The **top of the food chain**. A hospital group, clinic, or RCM company.

| Column | What it means |
|---|---|
| `id` | Unique ID (like a hospital registration number) |
| `name` | "City General Hospital" |
| `slug` | Web-friendly name: "city-general-hospital" |
| `type` | Is it a hospital? Clinic? RCM vendor? |
| `is_active` | Can this org log in? (TRUE/FALSE) |

**Real-world analogy:** Think of this as the *hospital corporation* registered with the government.

---

### `branches` table
Each **physical location or department** of the hospital.

| Column | What it means |
|---|---|
| `organization_id` | Which hospital does this branch belong to? |
| `name` | "Main Campus — Cardiology" |
| `code` | Short code: "CGH-CARD" |
| `city`, `state` | Where is it physically located? |

**Real-world analogy:** Apollo Hospitals is the organization. Apollo MRC Nagar and Apollo Greams Road are branches.

---

### `users` table
Actual **people** who log in and use the system.

| Column | What it means |
|---|---|
| `organization_id` | Which hospital do they work for? |
| `branch_id` | Which specific branch? (NULL = all branches) |
| `email` | Login email |
| `role` | What can they do? |

**Three roles explained simply:**

| Role | What they can do |
|---|---|
| `admin` | See everything across the whole hospital. Manage users. |
| `auditor` | Read-only. Reviews results. Cannot submit cases. |
| `coder` | Submits clinical documents. Sees only their branch's results. |

---

## Part 2: The Medical Reference Tables (Migrations 002–003)

These are like **medical encyclopaedias** — fixed reference data, not changing daily.

### `icd_codes` table
The official list of disease billing codes. Like a dictionary of every possible diagnosis.

```
ICD code E11.22 = "Type 2 diabetes with diabetic chronic kidney disease, stage 3"
ICD code I10    = "Essential hypertension"
ICD code A41.9  = "Sepsis, unspecified organism"
```

| Column | What it means |
|---|---|
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
