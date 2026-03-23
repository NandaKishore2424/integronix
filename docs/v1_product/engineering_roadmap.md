# Integronix — Engineering Roadmap
## Virtusa Jatayu Hackathon · Next Work Items (Assignable)

> **Problem Statement Alignment**
> Integronix is an AI-driven **hospital-side coding assistant and pre-validation tool** for the Indian healthcare industry.
> - Hospitals use it to extract ICD/CPT codes from discharge PDFs, validate claims, and submit to payers.
> - Payers receive a structured, auditable claim (FHIR + EDI) with AI confidence scores and a deterministic trust gate.
> - The system replaces error-prone manual coding without replacing payer adjudication engines.

---

## Current state (as of 2026-03-20)

| Layer | Status |
|-------|--------|
| PDF upload → ICD-11 pipeline (8-node LangGraph) | ✅ Working |
| CPT semantic matching (cpt_hcpcs_codes table) | ✅ Working |
| Financial summary (CPT × org multiplier) | ✅ Working |
| FHIR Condition (hospital coded diagnoses) | ✅ Working |
| FHIR Claim Proposal (hospital proposed, stored in claim_data) | ✅ Working |
| Payer Policy Gate (deterministic, payer-configurable) | ✅ Working |
| Auto-approve (PAID / PARTIALLY_PAID on gate PASS) | ✅ Working |
| Payer adjudication UI (approve / deny + audit log) | ✅ Working |
| EDI 837 export | ⚠️ Simulated (segments exist but not derived from FHIR) |
| Payer edit codes workflow | ❌ Not built |
| EDI 835 (remittance / denial response) | ❌ Not built |
| cpt_codes / financial_summary persisted to DB | ✅ Persisted |
| Tests (regression / golden set) | ❌ None |

---

## Work Items (pick and assign)

---

### TICKET-01 · Persist cpt_codes + financial_summary in coding_results
**Priority: HIGH (must-fix before demo)**
**Assigned to:** Backend engineer
**Status:** ✅ Completed

#### Problem
When a coder re-opens a case from Case History, `cpt_codes` and `financial_summary` are `[]` / `null` because they were never stored in the `coding_results` DB row. The payer gate then shows `NO_CPT_CODES` on re-submit.

#### What to do
1. **Migration** (`migrations/schema/019_coding_results_cpt_financial.sql`):
```sql
ALTER TABLE coding_results
    ADD COLUMN IF NOT EXISTS cpt_codes      JSONB,
    ADD COLUMN IF NOT EXISTS financial_summary JSONB;
```

2. **Backend write** (`backend/agents/risk_scoring.py` — this is the node that already writes to `coding_results`):
   Find the existing `upsert` / `insert` call into `coding_results` and add:
```python
"cpt_codes":        state.get("cpt_codes", []),
"financial_summary": state.get("financial_summary"),
```

3. **Backend read** (`backend/routes/cases.py`, line ~246):
   Already patched to read `result.get("cpt_codes")` and `result.get("financial_summary")`. Once DB has the columns, these will hydrate correctly.

4. **Verify**: Upload PDF → check Supabase `coding_results` row has `cpt_codes` populated → re-open case from history → submit claim → payer gate should show CPT present.

#### Files touched
- `migrations/schema/019_coding_results_cpt_financial.sql` (new)
- `backend/agents/risk_scoring.py` (add columns to upsert)

---

### TICKET-02 · Fix FHIR Claim financial amounts (use gross_charge not base_price)
**Priority: HIGH (data correctness)**
**Assigned to:** Backend engineer
**Status:** ✅ Completed

#### Problem
`build_fhir_claim_proposal()` currently uses `line_items[].base_price` (CMS base price) for FHIR `Claim.item[].unitPrice` and `net`. But `base_price` ignores the hospital's CPT pricing multiplier. If a hospital has `cpt_pricing_multiplier = 1.5`, the FHIR total would be wrong (underreported by 33%).

#### What to do
In `backend/services/fhir_claim_builder.py`, change this line:
```python
base_price = float(item.get("base_price") or item.get("cms_base_price") or 0.0)
```
to:
```python
# Prefer the hospital-multiplied gross charge; fall back to base if missing
base_price = float(
    item.get("gross_charge") or
    item.get("base_price") or
    item.get("cms_base_price") or 0.0
)
```

#### Files touched
- `backend/services/fhir_claim_builder.py` (1-line change, ~line 148)

---

### TICKET-03 · Real EDI 837 from payer-verified FHIR Claim
**Priority: HIGH (Jatayu demo story requires real interoperability)**
**Assigned to:** Backend engineer (senior)
**Status:** ✅ Completed

#### Problem
The current `GET /claims/export/edi/{id}` generates fake EDI segments (NM1, CLM, DTP) but doesn't use the FHIR Claim Proposal data stored in `claim_data.fhir_claim_proposal`. It can't carry ICD-11 codes in the correct EDI loop format and patient demographics are placeholders.

#### What to do
Create `backend/services/edi_837_builder.py`:

```python
def build_edi_837(fhir_claim: dict, org_name: str, payer_name: str) -> str:
    """
    Derive an EDI 837 Professional/Institutional claim string from
    the FHIR Claim proposal stored in claim_data.
    
    Segments needed for Indian payer demo:
    ISA (interchange control header)
    GS  (functional group header)
    ST  (transaction set header - 837)
    BHT (beginning of hierarchical transaction)
    NM1*41 (submitter = hospital)
    NM1*40 (receiver = payer)
    HL*1   (billing provider loop)
    NM1*85 (billing provider name)
    HL*2   (subscriber loop)
    NM1*IL (member/patient)
    DMG    (date of birth + sex, from FHIR contained Patient)
    CLM    (claim information - total billed)
    DTP*434 (service date range)
    HI     (ICD diagnosis codes - one per FHIR Claim.diagnosis[])
    LX     (service line counter)
    SV1    (professional service - CPT code + charge, from FHIR Claim.item[])
    SE     (transaction set trailer)
    GE     (functional group trailer)
    IEA    (interchange control trailer)
    """
```

Wire it in `backend/routes/claims.py` → `GET /claims/export/edi/{id}`:
- Fetch the claim row
- Extract `claim_data.fhir_claim_proposal`
- Call `build_edi_837(fhir_proposal, org_name, payer_name)`
- Return as `.edi` download

#### Key rules
- ICD loop: HI segment uses `ABK` qualifier for principal ICD-11 code, `ABF` for secondaries.
- CPT loop: SV1 uses ABO qualifier with the CPT code and charge.
- If `patient_dob` is missing (none in claim), omit DMG segment (don't invent it).

#### Files touched
- `backend/services/edi_837_builder.py` (new)
- `backend/routes/claims.py` (replace simulated EDI export with real builder call)

---

### TICKET-04 · Payer Edit Codes Workflow
**Priority: MEDIUM-HIGH (core payer trust feature)**
**Assigned to:** Full-stack engineer
**Status:** ✅ Completed

#### Problem
Right now, a payer can only Approve or Deny. In reality, payers routinely **edit codes** before approving (e.g., change the principal ICD from DC11.0&XA8KL9 to a less specific one). Integronix needs to store this for audit and dispute resolution.

#### What to do

**Backend:**

1. Migration (`migrations/schema/020_payer_code_edits.sql`):
```sql
CREATE TABLE payer_code_edits (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id        UUID REFERENCES claims(id) ON DELETE CASCADE,
    edited_by       UUID,           -- payer user id
    original_codes  JSONB,          -- hospital proposed ICD/CPT codes
    edited_codes    JSONB,          -- payer-corrected codes
    edit_reason     TEXT NOT NULL,  -- payer must provide a reason
    edited_at       TIMESTAMPTZ DEFAULT NOW()
);
```

2. Add column to `claims` table:
```sql
ALTER TABLE claims ADD COLUMN IF NOT EXISTS payer_edited BOOLEAN DEFAULT FALSE;
ALTER TABLE claims ADD COLUMN IF NOT EXISTS payer_edit_reason TEXT;
```

3. New endpoint: `POST /api/v1/claims/edit/{claim_id}` in `backend/routes/claims.py`:
```python
class PayerEditRequest(BaseModel):
    edited_icd_codes: List[dict]
    edited_cpt_codes: List[dict]
    edit_reason: str   # required

@router.post("/edit/{claim_id}")
async def payer_edit_claim(claim_id: str, req: PayerEditRequest):
    # 1. Fetch claim → check status is SUBMITTED
    # 2. Insert into payer_code_edits (original from claim_data, edited from req)
    # 3. Update claim.payer_edited = true, payer_edit_reason = req.edit_reason
    # 4. Insert audit log: SUBMITTED → PAYER_EDITED
```

**Frontend (`frontend/src/app/payer/adjudicate/[id]/page.tsx`):**
- Add "Edit Codes" section (only visible when `claim.status === 'SUBMITTED'`)
- Simple table: one row per ICD/CPT code, with an editable text field
- Reason input field (required)
- "Save Edits" button → calls `POST /api/v1/claims/edit/{id}`
- After save, re-load claim and show "Edited by Payer" badge

#### Files touched
- `migrations/schema/020_payer_code_edits.sql` (new)
- `backend/routes/claims.py` (new endpoint)
- `frontend/src/app/payer/adjudicate/[id]/page.tsx` (edit UI section)
- `frontend/src/lib/api.ts` (add `payerEditClaim()` function)

---

### TICKET-05 · EDI 835 Remittance Advice (payer → hospital)
**Priority: MEDIUM (Jatayu bonus story)**
**Assigned to:** Backend engineer
**Status:** ✅ Completed

#### Problem
After a payer approves/denies a claim, the hospital needs a structured response. EDI 835 (Healthcare Claim Payment/Advice) is the standard. This completes the claim lifecycle loop.

#### What to do
Create `backend/services/edi_835_builder.py`:

```python
def build_edi_835(claim: dict, adjudication_result: dict) -> str:
    """
    EDI 835 segments for payment advice:
    ISA / GS / ST (835)
    BPR  (financial information - total paid amount, currency INR)
    TRN  (trace number - use claim_id)
    REF  (payer reference)
    DTM  (payment date)
    N1*PR (payer name)
    N1*PE (provider/hospital name)
    CLP  (claim-level payment - CLM01=claim_id, CLM02=status, CLM03=billed, CLM04=paid)
    NM1*QC (patient name from claim.patient_name)
    SVC  (service line - CPT code, billed, paid)
    CAS  (adjustment reasons - contractual, patient responsibility)
    SE / GE / IEA
    """
```

Add endpoint: `GET /api/v1/claims/export/edi835/{claim_id}` in `backend/routes/claims.py`:
- Only callable when claim status is PAID/PARTIALLY_PAID/DENIED
- Returns `.835` file download

**Frontend (hospital coder view):**
- In `frontend/src/app/hospital/claims/page.tsx` (or equivalent case history page), add a "Download EDI 835" button next to each PAID/DENIED claim.

#### Files touched
- `backend/services/edi_835_builder.py` (new)
- `backend/routes/claims.py` (new endpoint)
- Frontend hospital claims/history page (download button)

---

### TICKET-06 · E2E Pipeline Regression Test Suite
**Priority: HIGH (demo safety)**
**Assigned to:** Automation / Backend
**Status:** ✅ Completed

#### Problem
Every time we change the pipeline (CPT resolver, FHIR builder, payer gate), we risk silently breaking something. The demo requires a consistent end-to-end flow.

#### What to do
Create `backend/tests/test_e2e_pipeline.py`:

```python
"""
Golden-set regression test:
Given the synthetic Priya Raman PDF, the pipeline must produce:
- final_icd_code: starts with "DC11"
- mapping_path: "who_api_icd11"
- cpt_codes: len >= 1
- cpt_codes[0]["code"]: "47562"
- financial_summary.total_estimated_revenue: ~541.28
- confidence_score: >= 0.80
- risk_score: < 0.15

Claims submit must produce:
- fhir_claim_proposal present
- fhir_claim_proposal.item[0].productOrService.coding[0].code == "47562"
- fhir_claim_proposal.total.value == 541.28
- fhir_claim_proposal.diagnosis[0].diagnosisCodeableConcept.coding[0].system includes "icd/release/11"
- payer_gate_report.gate_status == "PASS"
"""
```

Run with: `cd backend && pytest tests/test_e2e_pipeline.py -v`

#### Files touched
- `backend/tests/test_e2e_pipeline.py` (new)
- `backend/tests/fixtures/priya_raman_discharge.pdf` (copy the test PDF here)

---

### TICKET-07 · UI Polish for Demo Day
**Priority: MEDIUM (visual impression matters for hackathon)**
**Assigned to:** Frontend engineer

#### Problem
Several small UI inconsistencies make the demo look unfinished:
- "Billed Procedures (CPT)" section shows `$ base` (dollar sign) instead of `₹`
- CPT amount in the payer adjudication view is inconsistently formatted
- "STANDARD: ICD-10-CM 2024" is hardcoded — should show "WHO ICD-11" when Saveetha uses ICD-11
- Risk score is shown as `0.0987/100` instead of just `10%` or `0.10`

#### What to do

**File: `frontend/src/app/payer/adjudicate/[id]/page.tsx`**
- Line ~167: change `$${cpt.cms_base_price} base` → `₹${(cpt.cms_base_price ?? 0).toLocaleString('en-IN')} base`

**File: `frontend/src/components/ResultsPanel.tsx`**
- "STANDARD" label: use `result.mapping_path?.includes('icd11') ? 'WHO ICD-11' : 'ICD-10-CM 2024'`

**File: `frontend/src/app/payer/adjudicate/[id]/page.tsx`**
- Risk score: `{(riskScore * 100).toFixed(0)}%` instead of raw value

**File: `frontend/src/app/payer/adjudicate/[id]/page.tsx`**
- CPT line: show ₹541.28 in FHIR proposal section (already uses `toLocaleString('en-IN')` — verify this is consistent)

---

### TICKET-08 · Multi-tenant Demo Readiness (second hospital/payer)
**Priority: LOW-MEDIUM (nice-to-have for Jatayu story)**
**Assigned to:** Backend + seed data

#### Problem
Currently only Saveetha Hospitals + Global Health Insurance is demoed. Adding a second hospital (ICD-10, different multiplier) would show multi-tenancy is real.

#### What to do
1. Add seed data for a second organization in `migrations/seeds/`:
```sql
INSERT INTO organizations (id, name, slug, type, country, timezone) VALUES
  ('...', 'Apollo Hospitals', 'apollo-hospitals', 'hospital', 'IN', 'Asia/Kolkata');

INSERT INTO org_settings (organization_id, icd_version, cpt_pricing_multiplier) VALUES
  ('...', 'ICD-10', 1.2);
```

2. Add a second payer (e.g., "Star Health Insurance") with different auto-approve thresholds.

3. Run the pipeline with Apollo → confirm ICD-10 codes appear (not ICD-11 WHO path).

4. Run the pipeline with Saveetha → confirm ICD-11 still appears.

#### Files touched
- `migrations/seeds/004_apollo_demo_tenant.sql` (new)

---

## Summary table for assignment

| Ticket | Feature | Owner | Priority | Files |
|--------|---------|-------|----------|-------|
| 01 | ✅ Persist cpt_codes + financial_summary in DB | Backend | HIGH | `019_*.sql`, `risk_scoring.py` |
| 02 | ✅ Fix FHIR financial amounts (gross vs base) | Backend | HIGH | `fhir_claim_builder.py` |
| 03 | ✅ Real EDI 837 from FHIR proposal | Backend Senior | HIGH | `edi_837_builder.py`, `claims.py` |
| 04 | ✅ Payer edit codes UI + backend | Full-stack | MEDIUM-HIGH | `020_*.sql`, `claims.py`, adjudicate page, `api.ts` |
| 05 | EDI 835 remittance (payer → hospital) | Backend | MEDIUM | `edi_835_builder.py`, `claims.py`, hospital UI |
| 06 | E2E regression test suite | QA/Backend | MEDIUM | `tests/test_e2e_pipeline.py` |
| 07 | UI polish (₹, ICD standard label, risk %) | Frontend | MEDIUM | `ResultsPanel.tsx`, adjudicate page |
| 08 | Second hospital/payer seed (multi-tenant) | Backend | LOW-MEDIUM | `004_apollo_demo_tenant.sql` |

---

## Problem statement alignment check

| Jatayu requirement | Where we address it |
|--------------------|---------------------|
| AI-driven medical coding | LangGraph pipeline (9 nodes, WHO ICD-11, CPT semantic match) |
| ICD code extraction from PDFs | Node 2 (LLM extraction) + Node 5 (WHO API) |
| Coding accuracy + confidence | `confidence_score` from ICD decision node, risk score from risk_scoring node |
| Claim validation before payer submission | Payer Policy Gate (`services/payer_policy_gate.py`) |
| Payer trust (not a black box) | `payer_gate_report` with per-reason explanations |
| Interoperability (FHIR, EDI) | FHIR Condition + FHIR Claim Proposal (done), EDI 837 (TICKET-03), EDI 835 (TICKET-05) |
| Indian healthcare (ICD-11, INR, multi-tenant) | WHO ICD-11 path for ICD-11 orgs; INR currency; org_settings per hospital |
| Auditability | `claim_audit_logs` table + payer gate reasons in claim payload |
| Auto-approve workflow | `auto_approve_enabled` payer policy flag + deterministic gate |
