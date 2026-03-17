# 25 — Hospital Revenue Cycle: Full Workflow, Pain Points & Integronix Solution

> **Document Type:** Strategic & Technical Reference  
> **Created:** 2026-03-11  
> **Audience:** Product, Engineering, Sales, Hackathon Judges  
> **Purpose:** End-to-end explanation of how hospitals process clinical documentation into reimbursement — and exactly where Integronix automates and fixes the broken parts.

---

## PART 1: THE FULL HOSPITAL REVENUE CYCLE — FROM PATIENT TO PAYER

> *"The average hospital loses 3–5% of net revenue annually to coding errors alone."*  
> — HFMA (Healthcare Financial Management Association)

---

### STAGE 1: Patient Arrives at the Hospital

**What happens:**
- Patient presents at the ER, OPD (Outpatient Department), or is admitted via planned surgery
- Registration staff collect: name, address, date of birth, insurance details (payer name, plan ID, policy number), referring physician
- A **Medical Record Number (MRN)** is generated — this is the patient's permanent identifier in the hospital system
- Insurance is **verified in real-time** (or manually by calling the insurer) — checks co-pay, deductible, pre-authorization requirements
- If it's an inpatient admission, a **bed is assigned** and the patient's case is "opened" in the hospital EHR

**Tools used:** Hospital Information System (HIS), EHR (Epic, Cerner, Meditech), insurance eligibility verification portals  
**Time:** 15–45 minutes  
**Where it lags:** Manual insurance verification — staff call insurer, hold for 10–30 minutes. Prior authorization for procedures can take 1–3 days.

---

### STAGE 2: Clinical Care — The Physician Documents Everything

**What happens (this is where the coding story starts):**
- Attending physician writes an **Admission Note** + **History & Physical (H&P)** — documents why the patient is here, past medical history, current medications, vitals
- Every day of the inpatient stay, the physician writes a **Progress Note** (SOAP format: Subjective, Objective, Assessment, Plan)
- Specialists write **Consultation Reports** when called in (e.g., cardiologist, nephrologist)
- **Nursing Notes** are written every 4–8 hours — vital signs, medication administration, patient response
- Lab results, radiology reports (CT scan, X-ray, MRI), pathology reports are generated and attached to the patient's record
- Any surgery generates an **Operative Report** — 5–20 pages detailing incisions, findings, anatomy, sutures, complications

**What gets documented in writing:**
```
Admission Note → History & Physical → Daily Progress Notes (×N days)
→ Consultation Reports → Lab / Radiology / Pathology Reports
→ Operative Report (if procedure) → Nursing Notes → Discharge Summary
```

**Tools used:** EHR (physician typing directly), voice-to-text dictation software (Dragon Medical), paper in rural hospitals  
**Time:** Ongoing throughout stay  
**Where it lags:**
- Physicians are busy — documentation is often incomplete, vague, or delayed
- They say "diabetes" instead of "Type 2 diabetes mellitus with CKD stage 3" — coders cannot code what isn't written
- Handwriting in paper records is often illegible
- Some hospitals still use paper discharge summaries that are then **scanned and saved as PDFs**

---

### STAGE 3: Discharge — The Discharge Summary is Created

**This is the most critical document for medical coding.**

**What happens:**
- When the patient is ready to go home, the attending physician writes the **Discharge Summary**
- This is a 2–10 page structured document containing:
  - **Admitting Diagnosis** — what problem brought the patient in
  - **Hospital Course** — what happened day by day
  - **Procedures Performed** — surgeries, dialysis, biopsies, endoscopies
  - **Significant Lab/Imaging Findings** — HbA1c 9.2%, eGFR 42 mL/min, CT findings
  - **Final/Discharge Diagnoses** — physician's final conclusions after all tests
  - **Discharge Medications** — drugs, doses, frequency, new vs changed
  - **Discharge Condition** — stable / improved / deteriorated
  - **Follow-up Instructions** — which specialist, when, what to watch for
- Physician signs the summary (physical or electronic signature)
- In most Indian hospitals: printed → signed → scanned → saved as PDF
- In US hospitals with full EHR: discharge summary stays digital inside Epic/Cerner

**Format example (a real discharge summary looks like this):**
```
PATIENT: John D.  MRN: 4838201  Admission: 02-Mar-2026  Discharge: 08-Mar-2026

ADMITTING DIAGNOSIS: Shortness of breath, elevated blood glucose

DISCHARGE DIAGNOSES:
1. Type 2 Diabetes Mellitus with Diabetic Chronic Kidney Disease Stage 3
2. Hypertensive Heart Disease
3. Anemia of Chronic Disease

HOSPITAL COURSE:
Patient presented with dyspnea and fatigue. HbA1c found to be 9.4%.
eGFR measured at 42 mL/min consistent with CKD Stage 3...

PROCEDURES: None surgical. IV insulin infusion × 3 days.

DISCHARGE MEDICATIONS:
• Lisinopril 10mg OD (continued)
• Metformin 500mg BD (dose reduced due to CKD)
• Insulin Glargine 20 units at bedtime (NEW)
...
```

**Tools used:** EHR discharge module or MS Word template, sometimes dictated via Dragon  
**Time:** 2–4 hours for physician to complete (often delayed 24–72 hours after discharge — a major compliance issue)  
**Where it lags:**
- Physicians often copy-paste from old notes, introducing outdated diagnoses
- Final diagnosis list is sometimes incomplete — comorbidities (like CKD) are mentioned in the body but not listed in the final diagnosis section
- Summary is not specific enough — "hypertension" instead of "Stage 2 hypertension with hypertensive CKD", losing reimbursement specificity
- Scanned PDF quality is often poor — faded ink, skewed pages, handwritten annotations

---

### STAGE 4: The Discharge Summary Reaches the Medical Coder

**This is the exact entry point where Integronix operates.**

**What happens today (without Integronix):**
- Discharge summary PDF lands in the **coding queue** — a shared drive, email inbox, or coding module inside the hospital's HIS
- Coder (a trained CPC/CCS certified professional) opens the PDF on their screen
- They read the **entire document** manually — 2–10 pages
- They identify all **codeable diagnoses** — not just the primary, but secondary, tertiary, comorbidities, complications
- They look up each condition in the **ICD-10-CM code book** (a 1,000+ page book, now queried via software like EncoderPro, 3M, TruCode)
- They assign:
  - **Primary Diagnosis Code (PDX)** — main reason for admission
  - **Secondary Diagnosis Codes (SDX)** — comorbidities and complications that affect care or resources
  - **Procedure Codes** — ICD-10-PCS for inpatient, CPT for outpatient
- They flag any **Complications/Comorbidities (CC)** and **Major Complications/Comorbidities (MCC)** — these dramatically affect DRG weight and reimbursement
- They submit codes to the billing team

**How long this takes per case:**
- Simple case (short stay, 1-2 diagnoses): 20–40 minutes
- Complex case (long stay, multiple diagnoses, surgery): 1–3 hours
- A busy hospital generates 100–500 cases/day — needs a team of 5–50 coders

**Tools used:** PDF viewer, EncoderPro/3M360/TruCode (code lookup software), Excel spreadsheets for tracking, hospital HIS/billing module  
**Where it lags (the biggest pain points):**
1. **Manual reading** — completely manual, no AI assistance
2. **Missing specificity** — coder codes what they see; if discharge summary says "diabetes", they code E11.9 (unspecified) — missing +$900 in reimbursement vs E11.22 (with CKD)
3. **Missed secondary codes** — a skilled coder catches CKD as a secondary diagnosis; an inexperienced one misses it entirely
4. **Volume pressure** — coders are pressured to do 25–40 cases/day; complex cases get rushed
5. **Knowledge gaps** — ICD-10-CM has 70,000+ codes; subtle differences affect reimbursement significantly
6. **No real-time validation** — errors not caught until claim denial, weeks later
7. **Audit fear** — overcoding (billing for higher severity than documented) triggers audits; undercoding (billing less than warranted) loses revenue

---

### STAGE 5: Code Validation & Query (CDI — Clinical Documentation Improvement)

**What happens in well-run hospitals:**
- CDI specialists (Clinical Documentation Improvement) review the coder's work before submission
- If the coder wants to assign a more specific code (e.g., E11.22) but the discharge summary only says "diabetes with kidney disease", CDI sends a **Query** to the physician
- Physician responds with clarification: "Yes, patient has CKD Stage 3"
- Coder updates the code
- This query back-and-forth takes **2–5 business days** in most hospitals
- Many hospitals skip CDI entirely due to staffing costs

**Tools used:** Optum CDI, 3M CDI, manual email/phone queries to physicians  
**Where it lags:**
- Query response time is 2–5 days → delays the entire billing cycle
- Physicians resent queries — too many causes "query fatigue"
- Small hospitals have no CDI team at all — coders submit without review
- Queries are formatted inconsistently — sometimes accepted, sometimes rejected by payers

---

### STAGE 6: Claim Creation & Submission to Payer

**What happens:**
- Validated codes (ICD-10-CM diagnoses + CPT/ICD-10-PCS procedures) are loaded into the **billing system** (Meditech, Cerner Revenue Cycle, Athenahealth, Epic Resolute, or standalone like AdvancedMD)
- A **UB-04 form** (for hospital inpatient/outpatient claims) or **CMS-1500 form** (for physician billing) is auto-generated
- Key fields: patient demographics, payer details, dates of service, ICD-10 codes, procedure codes, charges per service line
- Claim goes through **internal scrubbing** — checks for basic errors: invalid codes, missing modifiers, duplicate claims, out-of-sequence dates
- Clean claim is submitted **electronically** via EDI 837 transaction to the payer (insurance company)

**Tools used:** Hospital billing system (Epic, Meditech), claim scrubber (ClaimLogic, Waystar), clearinghouse (Change Healthcare, Availity)  
**Time from discharge to claim submission:** 2–10 business days  
**Where it lags:**
- Rejected claims at scrubbing stage — wrong code, unlisted procedure, missing modifier → return to coder → fix → resubmit (+2–5 days)
- Claims with "unbundling" issues — billing separately for procedures that must be bundled → payer rejection

---

### STAGE 7: Payer Adjudication — The Insurance Company Reviews the Claim

**What happens:**
- Payer (e.g., BCBS, Medicare, Aetna, government insurer) receives the EDI 837 claim
- Automated adjudication system runs:
  1. **Eligibility check** — is the patient still covered? Is this date within the policy period?
  2. **Authorization check** — was prior auth obtained?
  3. **Medical necessity review** — do the diagnosis codes justify the procedures?
  4. **Coverage check** — is this diagnosis/procedure covered under this plan?
  5. **DRG assignment** — for inpatient, the claim is assigned a **Diagnosis-Related Group (DRG)** based on the principal diagnosis, procedures, patient age, and CC/MCC presence
  6. **Payment calculation** — DRG base rate × facility adjustment × case mix index = reimbursement

**What is DRG and why it matters:**
- DRG = a classification system for inpatient hospital stays
- Each DRG has a **base payment rate** (e.g., DRG 638 = $5,200 for simple diabetes)
- Adding a CC (complication/comorbidity) upgrades to a higher-paying DRG (e.g., $7,100)
- Adding an MCC (major complication) upgrades further (e.g., $12,400)
- **One missed diagnosis code = wrong DRG = potentially thousands of dollars lost per case**

**Time:** 14–45 days from claim submission  
**Where it lags:**
- Claims can be **denied** for many reasons: medical necessity, incorrect coding, missing documentation, authorization failure
- **Denial rate** in US hospitals: 5–15% of all claims are initially denied
- Each denial costs ~$25–$118 to rework (MGMA data)

---

### STAGE 8: Explanation of Benefits (EOB) & Payment Posting

**What happens:**
- Payer sends an **EOB (Explanation of Benefits)** — a breakdown of: amount billed, amount approved, amount paid, patient responsibility, reason codes for any denials/reductions
- Billing team posts payment to the patient account
- If underpaid: appeals process begins (can take weeks to months)
- Patient receives a bill for their **co-pay + deductible + co-insurance**
- Collections team follows up on outstanding patient balances

**Time from claim submission to payment:** 30–90 days  
**Where it lags:**
- Manual payment posting from paper EOBs
- Appeals process is time-intensive and success rates vary

---

### STAGE 9: Denial Management & Appeals

**What happens when a claim is denied:**
- Denial reason code is analyzed (e.g., CO-50 = not medically necessary; CO-4 = incorrect code)
- Coding team reviews and corrects
- Medical records attached
- Appeal submitted to payer — Level 1 (internal), Level 2 (external), and in rare cases, arbitration

**Time:** 30–180 days per appeal  
**Where it lags:** Manual, slow, expensive, and often unsuccessful without proper documentation matching

---

## PART 2: WHERE INTEGRONIX FITS — THE AGENTIC AI AUTOMATION LAYER

```
HOSPITAL WORKFLOW                   INTEGRONIX AUTOMATION
──────────────────                  ─────────────────────
[Stage 1] Patient Registration      ─ Not in scope (registration software)
[Stage 2] Clinical Documentation    ─ Future: CDI alerts to physician
[Stage 3] Discharge Summary         ─ ✅ INPUT: PDF upload + OCR extraction
[Stage 4] Manual Coding             ─ ✅ CORE: Agentic AI replaces manual reading
[Stage 5] CDI Query Loop            ─ ✅ AUTOMATED: AI flags before physician query needed
[Stage 6] Claim Creation            ─ 🔄 Future: FHIR R4 export to billing system
[Stage 7] Payer Adjudication        ─ 🔄 Future: Pre-submission DRG prediction
[Stage 8] Payment Posting           ─ Not in scope
[Stage 9] Denial Management         ─ 🔄 Future: Denial prediction & pre-emptive correction
```

---

### 2.1 How Integronix Works: The 8-Node Agentic AI Pipeline

When a coder uploads a discharge summary PDF (or pastes clinical text), Integronix runs a deterministic 8-node LangGraph pipeline that completes in under 2 seconds:

```
PDF / Clinical Text Input
         │
         ▼
[Node 1] Document Processor
   • Extracts raw text from PDF (digital: PyMuPDF, scanned: Tesseract OCR)
   • Detects document type: Discharge Summary / SOAP Note / Operative Report
   • Cleans and normalises text
         │
         ▼
[Node 2] Clinical Extractor (LLaMA 3.3-70B via Groq API)
   • Identifies diagnoses, conditions, procedures using LLM reasoning
   • Extracts: primary condition, comorbidities, lab values, medications
   • Output: structured clinical entities JSON
   • Latency: ~700ms (Groq's blazing-fast inference)
         │
         ▼
[Node 3] SNOMED Resolver
   • Maps each extracted clinical term to SNOMED CT concept ID
   • Uses a pre-built lookup table (snomed_icd_mapper)
   • SNOMED is the gold standard clinical terminology — more precise than raw text
         │
         ▼
[Node 4] ICD-10 Direct Mapper
   • Looks up SNOMED → ICD-10-CM crosswalk from Supabase (PostgreSQL)
   • Retrieves candidate ICD codes for each clinical entity
   • Finds specificity options (e.g., E11.9 vs E11.22 vs E11.65)
         │
         ▼
[Node 5] Embedding Fallback (pgvector similarity search)
   • For conditions not found via direct crosswalk
   • Generates semantic embeddings (sentence-transformers/all-MiniLM-L6-v2)
   • Finds closest ICD codes by cosine similarity in the 71,000-code vector database
   • Ensures no condition is left uncoded
         │
         ▼
[Node 6] ICD Decision Engine (Deterministic Scoring)
   • Ranks all candidate codes using a 7-factor scoring algorithm:
     1. Direct SNOMED match bonus (+40 pts)
     2. Semantic similarity score (0–30 pts)
     3. Code specificity (4-char > 3-char > 2-char) (+0–20 pts)
     4. CC/MCC presence (+15 pts for MCC, +10 for CC)
     5. Clinical context alignment (+10 pts)
     6. Negation penalty (−50 pts if "no", "without", "denies")
     7. Uncertainty penalty (−20 pts if "possible", "suspected")
   • Returns ranked list: primary code + secondary + additional codes
   • NO LLM hallucination in code selection — fully deterministic
         │
         ▼
[Node 7] Audit Comparison (if human code provided)
   • Compares AI code vs coder-submitted code
   • Detects discrepancy type:
     - SPECIFICITY_IMPROVEMENT — AI found more specific code
     - MCC_MISSED — AI found a Major Complication not coded
     - CC_MISSED — AI found a Complication not coded
     - OVERCODING — AI found human code is too aggressive
     - CORRECT — codes match
   • Sets DRG flag for revenue impact calculation
   • Revenue delta = |AI DRG base rate − Human DRG base rate|
         │
         ▼
[Node 8] Risk Scorer
   • Calculates audit risk probability (0–100%)
   • Factors: code mismatch severity, DRG gap, confidence score
   • DRG-aware MCC boost: +15% risk if MCC missed
   • Output: LOW / MEDIUM / HIGH risk + AI confidence %
   • Also generates FHIR R4 Condition resource for EHR integration
         │
         ▼
API Response → Frontend Dashboard
```

---

### 2.2 What Problems We Solve at Each Stage

| Pain Point (Without Integronix) | How Integronix Fixes It |
|---|---|
| Coder reads 10-page PDF manually for 90 minutes | AI reads and extracts in <1 second |
| Codes E11.9 (vague) when E11.22 (specific) is correct | Specificity scoring always finds the most detailed code |
| Misses CKD as secondary diagnosis | Multi-code output captures all diagnoses |
| Doesn't know revenue impact of wrong code | Revenue delta shown instantly (+$900, +$3,200, etc.) |
| CDI query to physician takes 2–5 days | AI flags the gap before submission — no query needed |
| Audit risk unknown until payer denies | Real-time audit risk score (17% LOW → 72% HIGH) |
| Paper PDF → code book lookup → billing system: 3 manual steps | PDF → AI → codes: 1 automated step |
| No FHIR output for EHR integration | FHIR R4 Condition resource generated automatically |
| Separate tools for coding + auditing | Unified platform: code + audit + risk in one |

---

## PART 3: COMPLETE FEATURE STATUS

### ✅ DONE — Production Ready

#### Backend — Agentic AI Pipeline
- [x] **Node 1: Document Processor** — raw text ingestion, text normalisation
- [x] **Node 2: Clinical Extractor** — LLaMA 3.3-70B via Groq API, structured entity extraction
- [x] **Node 3: SNOMED Resolver** — clinical term → SNOMED CT concept ID mapping
- [x] **Node 4: ICD-10 Direct Mapper** — SNOMED → ICD-10-CM crosswalk with Supabase
- [x] **Node 5: Embedding Fallback** — pgvector semantic similarity search (sentence-transformers)
- [x] **Node 6: ICD Decision Engine** — 7-factor deterministic scoring algorithm, multi-code ranked output (primary/secondary/additional with roles and rationale)
- [x] **Node 7: Audit Comparison** — AI vs human code comparison, discrepancy classification, DRG flag detection (MCC_MISSED, CC_MISSED, MCC_OVERCODED)
- [x] **Node 8: Risk Scorer** — DRG-aware risk scoring, LOW/MEDIUM/HIGH classification, FHIR R4 Condition resource generation
- [x] **FastAPI REST API** — `/api/v1/code/run` endpoint with full Pydantic schema
- [x] **CORS** — configured for frontend ports 3000 + 3001

#### Database — Supabase (PostgreSQL + pgvector)
- [x] **icd_codes** — 71,000+ ICD-10-CM codes with descriptions and CC/MCC flags
- [x] **snomed_concepts** — SNOMED CT terminology + ICD crosswalk mappings
- [x] **clinical_cases** — case storage with tenant columns (org, branch, submitted_by, document_source, ocr_used)
- [x] **coding_results** — AI pipeline outputs per case with tenant columns
- [x] **revenue_impact** — DRG base rate lookup table
- [x] **audit_log** — immutable audit trail of all coding decisions
- [x] **vector embeddings** — pgvector similarity search RPC function
- [x] **Multi-tenant architecture** — organizations, branches, users tables
- [x] **Row-Level Security (RLS)** — org isolation at database level via JWT app_metadata
- [x] **Demo seed data** — City General Hospital + 3 branches + 5 demo users

#### Frontend — Next.js 14 Dashboard
- [x] **Landing Page** (`/`) — hero, feature highlights, stats, CTA
- [x] **Login Page** (`/auth/login`) — email/password + Demo Access button
- [x] **Signup Page** (`/auth/signup`) — 2-step: org details → admin account creation
- [x] **Dashboard Layout** — fixed sidebar with org name, role-gated navigation, user avatar, sign out
- [x] **Analyse Page** (`/dashboard/analyze`) — two-tab UI: New Analysis + Report
- [x] **CodeInputPanel** — clinical text textarea, existing ICD code field, 3 sample cases, pipeline stage display
- [x] **IcdCodeCard** — recommended code, confidence bar, CC/MCC chip, SNOMED chain, DRG badge
- [x] **MultiCodeList** — primary/secondary/additional codes with roles, rationale, scores
- [x] **AuditCard** — side-by-side AI vs human comparison, discrepancy type, revenue delta
- [x] **RiskMeter** — SVG circular gauge (LOW/MEDIUM/HIGH), AI confidence %
- [x] **CandidateChart** — Recharts horizontal bar chart of all scored ICD candidates
- [x] **DrgBadge** — MCC/CC gap alert with pulsing indicator
- [x] **FhirPanel** — collapsible FHIR R4 JSON, copy-to-clipboard
- [x] **ResultsPanel** — orchestration wrapper for all result components
- [x] **Branches Page** (`/dashboard/branches`) — branch card grid, Add Branch modal
- [x] **Users Page** (`/dashboard/users`) — user table with role badges, Add User modal
- [x] **AuthProvider** — global auth context (authUser, orgUser, org, loading, signOut)
- [x] **Middleware** — Supabase SSR session management, route protection
- [x] **supabase.ts** — browser client, TypeScript types (OrgUser, Organization, Branch, UserRole)
- [x] **api.ts** — typed API client: `runCodingPipeline()` (JSON) + `runPdfPipeline()` (FormData) + `formatCurrency()` / `formatConfidence()` helpers
- [x] **types/coding.ts** — TypeScript interfaces matching backend Pydantic models, including `document_source` and `ocr_used`

#### Infrastructure & Docs
- [x] **README.md** — setup guide for new developers (clone → install → env → run)
- [x] **17 SQL Migration files** (001–017) with schema, indexes, RLS, seed data
- [x] **26 documentation files** in `/docs` covering architecture, algorithms, FHIR, SNOMED, auth, RCM workflow
- [x] **Docker compose** — local development setup

#### Phase 6A — PDF Upload Pipeline ✅ SHIPPED (2026-03-11)
- [x] **`POST /api/v1/code/run-pdf`** — multipart/form-data endpoint, validates file is PDF ≤ 20 MB, feeds bytes into Node 1
- [x] **`pdf_service.py`** — returns `(text, ocr_used: bool)` tuple. `False` = digital PDF via pdfplumber. `True` = scanned PDF via Tesseract OCR fallback
- [x] **`doc_processor.py`** — unpacks tuple, sets `document_source` and `ocr_used` in pipeline state
- [x] **`CodingState` + `CodeResponse`** — both now carry `document_source` and `ocr_used` fields
- [x] **`CodeInputPanel.tsx`** — complete rewrite: **Paste Text | Upload PDF** tab switcher, drag-and-drop zone with file validation, selected file info card, shared ICD code field for both modes
- [x] **`api.ts`** — added `runPdfPipeline(file, humanCode?)` sending FormData to `/code/run-pdf`
- [x] **`ResultsPanel.tsx`** — added `📄 Digital PDF` / `🔍 OCR Extracted` badge in summary strip

---

### 🔄 NEXT UP

#### Phase 6B — Case History / Audit Log Dashboard ✅ SHIPPED (2026-03-11)
- [x] **Migration 018** — added `icd_codes_full`, `drg_flag`, `fhir_condition` to `coding_results`; `raw_text_snippet` to `clinical_cases`; 4 performance indexes
- [x] **`risk_scoring.py`** — now writes full pipeline output to DB: `icd_codes_full`, `drg_flag`, `document_source`, `ocr_used`, `raw_text_snippet`, proper `case_id` FK linkage
- [x] **`database.py`** — added `select_paginated()` (PostgREST Range header) and `select_count()` helpers
- [x] **`routes/cases.py`** — three endpoints: `GET /cases` (paginated list + join), `GET /cases/stats` (KPI aggregates), `GET /cases/{session_id}` (full detail)
- [x] **`models.py`** — `CaseSummary`, `CaseListResponse`, `CaseStatsResponse` Pydantic models
- [x] **`main.py`** — cases router registered at `/api/v1`
- [x] **`types/cases.ts`** — TypeScript interfaces matching backend models
- [x] **`api.ts`** — `fetchCases()`, `fetchCaseStats()`, `fetchCaseDetail()` functions
- [x] **`/dashboard/cases/page.tsx`** — full page: 4 stat cards, filter bar (risk/source), paginated table, CSV export
- [x] **`/dashboard/cases/[session_id]/page.tsx`** — detail view reusing `ResultsPanel`, back-navigation
- [x] **`dashboard/layout.tsx`** — added "Case History" sidebar nav link with Clock icon

#### Phase 6C — Analytics Dashboard ✅ SHIPPED (2026-03-11)
- [x] **`routes/analytics.py`** — 3 endpoints: `GET /analytics/overview` (KPIs + 30-day trend), `GET /analytics/top-codes` (top 10 by frequency), `GET /analytics/discrepancy-breakdown` (type distribution)
- [x] **Pydantic models** — `TrendPoint`, `AnalyticsOverview`, `TopCodeItem`, `AnalyticsTopCodes` added to `models.py`
- [x] **`main.py`** — analytics router registered at `/api/v1`
- [x] **`types/analytics.ts`** — TypeScript interfaces for all analytics shapes
- [x] **`api.ts`** — `fetchAnalyticsOverview()`, `fetchTopCodes()`, `fetchDiscrepancyBreakdown()`
- [x] **`/dashboard/analytics/page.tsx`** — 4 KPI cards, dual-axis 30-day area chart (cases + revenue), top-10 ICD codes horizontal bar chart, risk distribution donut, discrepancy type donut. All with dark-theme tooltips, skeleton loading, and empty state
- [x] **`dashboard/layout.tsx`** — Analytics sidebar link added with BarChart3 icon

#### Phase 6D — Multi-page Document Support
- [ ] Extract and intelligently segment long PDFs (8–20 pages)
- [ ] Focus AI extraction on: Final Diagnosis section, Hospital Course, Discharge Medications
- [ ] Handle multi-column PDF layouts (common in scanned documents)

#### Phase 6E — CDI Query Assistant
- [ ] Auto-generate physician query when AI detects documentation gap
- [ ] Query template: "Based on your clinical note, the patient appears to have CKD Stage 3 (eGFR 42 mL/min). Can you confirm the final diagnosis for coding purposes?"
- [ ] Query management dashboard for CDI team

#### Phase 7A — EHR Integration
- [ ] FHIR R4 export to external EHR (Epic, Cerner) via SMART on FHIR
- [ ] Direct HL7 message generation for legacy HIS systems
- [ ] Webhook callbacks to billing system (Meditech, Athenahealth) on code completion

#### Phase 7B — Denial Prediction
- [ ] Pre-submission analysis: "This claim has 34% denial probability based on payer rules + code pattern"
- [ ] Top 3 denial reasons listed with recommended fixes
- [ ] Historical payer rule database per insurance type

---

## PART 4: MARKET CONTEXT — WHY THIS MATTERS

| Metric | Value | Source |
|---|---|---|
| Annual US healthcare revenue cycle loss to coding errors | $36 Billion | ACDIS/HFMA |
| Average coding error rate in US hospitals | 15–25% | OIG |
| Time a coder spends per complex case (manual) | 60–180 minutes | AAPC |
| Integronix analysis time | < 2 seconds | Measured |
| Revenue recovered per corrected E11.9 → E11.22 case | +$900/case | DRG table |
| A large hospital processing 300 cases/day | $270,000/day in potential revenue errors | Estimate |
| Percentage of hospitals using AI for coding (2024) | ~12% | Gartner | 
| Market opportunity (AI medical coding market 2027) | $6.2 Billion | Grand View Research |

---

## PART 5: INTEGRONIX COMPETITIVE POSITIONING

| Feature | Traditional Coding (Manual) | Competing AI Tools | **Integronix** |
|---|---|---|---|
| Input format | Text only (EHR) | Text, structured data | **Text + PDF + OCR** |
| ICD code selection method | Human judgment | Black-box LLM | **Deterministic 7-step algorithm** |
| Multi-code output | Yes (manual) | Limited | **Primary + Secondary + Additional with rationale** |
| DRG impact awareness | Expert coders only | Rare | **Built-in DRG flag + revenue delta** |
| Real-time audit comparison | No | No | **AI vs Human side-by-side with discrepancy type** |
| FHIR R4 output | No | No | **Auto-generated FHIR Condition resource** |
| Multi-tenant / hospital isolation | No (per-hospital software) | Some | **Full RLS-enforced org isolation** |
| Explainability | None | Low | **Full SNOMED → ICD chain, confidence scores, rationale** |
| Setup time | Months | Weeks | **Minutes (hosted, cloud-native)** |
| Hallucination risk | N/A | High | **Near-zero (LLM only extracts, deterministic engine selects)** |

---

*Document maintained by the Integronix engineering team. Update when new features ship.*
