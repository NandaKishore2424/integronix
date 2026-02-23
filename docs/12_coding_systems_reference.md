# 12 — Medical Coding Systems: ICD-10, SNOMED, LOINC, CPT

> Understanding these systems is critical for technical depth in Q&A and for correct data storage design.

---

## The 4 Systems and Their Roles

| System | Full Name | Used For | Managed By |
|---|---|---|---|
| **ICD-10-CM** | International Classification of Diseases, 10th Revision, Clinical Modification | Diagnoses, DRG grouping, claims | CMS / CDC |
| **CPT** | Current Procedural Terminology | Physician procedures, services | AMA |
| **SNOMED CT** | Systematized Nomenclature of Medicine Clinical Terms | Clinical EHR documentation, concepts | SNOMED International |
| **LOINC** | Logical Observation Identifiers Names and Codes | Lab tests, clinical observations | Regenstrief Institute |

---

## ICD-10-CM (Primary Focus for Integronix)

### What It Is
- The US clinical modification of ICD-10 (WHO standard)
- ~70,000+ diagnosis codes
- Used for: hospital billing, insurance claims, DRG grouping, public health reporting
- Updated annually (October release)

### Why It's Our Core
- All hospital reimbursement is ICD-10 driven
- DRG grouping depends on principal + secondary ICD codes
- CC/MCC status lives in ICD metadata
- Revenue delta calculation is ICD-specific

### Code Structure
```
E  1  1  .  2  2
│  │       └── Specificity detail (CKD stage)
│  │  └─────── Type 2 diabetes
│  └────────── Diabetes mellitus category
└───────────── Endocrine chapter
```

Code `E11.22` = Type 2 DM with diabetic chronic kidney disease

### Official Source
- **URL:** https://www.cdc.gov/nchs/icd/icd10cm.htm
- **Format:** Downloadable ZIP with XML and tabular files
- **License:** Public domain (US government data)
- **Update cycle:** Annual (October 1st effective date)

### Supabase Table (`icd_codes`)
```sql
CREATE TABLE icd_codes (
    code              TEXT PRIMARY KEY,             -- e.g. "E11.22"
    description       TEXT NOT NULL,               -- Full description
    chapter           TEXT,                        -- e.g. "Endocrine"
    category          TEXT,                        -- Sub-category
    is_billable       BOOLEAN DEFAULT TRUE,
    is_cc             BOOLEAN DEFAULT FALSE,       -- Complication/Comorbidity
    is_mcc            BOOLEAN DEFAULT FALSE,       -- Major CC
    version           TEXT DEFAULT '2024',
    system            TEXT DEFAULT 'ICD-10-CM',   -- Code system identifier
    base_reimbursement NUMERIC DEFAULT 0,          -- Simulated DRG value
    embedding         VECTOR(384)                  -- pgvector embedding
);
```

---

## CPT (Procedure Codes)

### What It Is
- Standardized codes for medical procedures and services
- ~10,000 codes (Category I, II, III)
- Required for outpatient and physician billing

### Relevance to Integronix
- Phase 2 expansion — we mention it architecturally
- POC focuses on diagnosis (ICD-10)
- Supabase table is designed to accommodate CPT later via `system` field

### Official Source
- **Owner:** American Medical Association (AMA)
- **License:** PAID — full dataset requires license
- **For hackathon:** Use limited public examples only
- **Note:** In pitch, say "CPT integration is in our Phase 2 roadmap"

---

## SNOMED CT (Clinical Terminology)

### What It Is
- World's largest, most comprehensive clinical healthcare terminology
- 350,000+ concepts with rich relationship hierarchy
- Used in EHRs for structured clinical documentation
- NOT primarily a billing system

### Why It Matters
- EHRs store diagnoses as SNOMED concepts
- Claims systems need ICD-10
- **SNOMED → ICD mapping is the bridge**
- Our system extracts SNOMED-like concepts and maps to ICD

### SNOMED Concept Example
```
Concept ID: 44054006
FSN: "Diabetes mellitus type 2 (disorder)"
Synonyms: "Type II diabetes mellitus", "T2DM"
```

### Official Source
- **URL:** https://www.snomed.org
- **License:** Requires license (many countries have national licenses)
- **For hackathon:** Use SNOMED-ICD cross-mapping files from NLM UMLS

### Supabase Table (`snomed_concepts`)
```sql
CREATE TABLE snomed_concepts (
    snomed_code  TEXT PRIMARY KEY,     -- e.g. "44054006"
    fsn          TEXT,                 -- Fully Specified Name
    description  TEXT,                 -- Human-readable
    hierarchy    TEXT                  -- Clinical category
);
```

---

## LOINC (Lab and Observation Codes)

### What It Is
- Universal codes for lab results, clinical measurements, observations
- 90,000+ codes
- Used for interoperability between health systems

### Examples
```
8480-6  = Systolic blood pressure
2160-0  = Creatinine [Mass/volume] in Serum
33914-3 = Glomerular filtration rate (eGFR)
```

### Relevance to Integronix
- Enriches clinical context (labs can influence ICD specificity)
- E.g., eGFR < 45 → CKD Stage 3 → ICD N18.3
- Architecture supports LOINC observations as context signals
- **Not required for POC; mention in roadmap**

### Official Source
- **URL:** https://loinc.org
- **License:** Free with registration
- **Download:** CSV format available

---

## How These Systems Relate (Clinical Data Flow)

```
Clinical Documentation (EHR)
         │
         │ Uses SNOMED concepts for clinical meaning
         ▼
Clinical Extraction Agent (LLM)
         │
         │ Extracts SNOMED-like structured clinical entities
         ▼
SNOMED → ICD Mapping Engine
         │
         │ Maps clinical concept to billing code
         ▼
ICD-10-CM Code (Deterministic from DB)
         │
         │ Used for...
         ├── DRG Grouper → Reimbursement
         ├── Claim Submission → Payer
         └── Audit Comparison → Revenue delta
```

LOINC observations can **augment specificity** at the SNOMED extraction step:
- Lab shows eGFR 42 → LOINC 33914-3 → maps to CKD Stage 3 → SNOMED concept → ICD N18.3

---

## What to Say in the Pitch About These Systems

> *"Integronix uses ICD-10-CM as the primary billing code system for deterministic mapping and revenue simulation. Our architecture is designed to support SNOMED-to-ICD mapping for EHR-sourced encounters and LOINC for lab-driven specificity enhancement. CPT integration for procedure coding is on our Phase 2 roadmap. Data storage follows FHIR resource alignment for healthcare interoperability."*

---

## Correct System URIs (FHIR Standard)

These are used in our FHIR-aligned JSON schemas:

| System | URI |
|---|---|
| ICD-10-CM | `http://hl7.org/fhir/sid/icd-10-cm` |
| CPT | `http://www.ama-assn.org/go/cpt` |
| SNOMED CT | `http://snomed.info/sct` |
| LOINC | `http://loinc.org` |
