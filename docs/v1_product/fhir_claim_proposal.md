# Feature V1.1: FHIR Claim Proposal (Hospital Proposed Artifact)

## Simple description
When a hospital uploads a PDF, Integronix already extracts clinical entities and recommends ICD/CPT codes.  
In V1.1 we will turn that recommendation into a **standards-based FHIR `Claim` proposal JSON** (internal artifact for the payer).

This FHIR `Claim` proposal becomes the “trustable evidence packet” for the payer UI:
- Payer can see what claim would be sent to insurance (diagnoses + procedures + demographics)
- Payer can apply their own policy/edits with transparency
- Later we can derive **EDI 837** from this verified claim (instead of the current simulated EDI)

## Why this feature (agentic alignment)
Use Case 2 is about a “real-time auditor / revenue integrity agent”.
This feature upgrades the “auditor” output from:
- codes + gate reasons
to
- a single auditable, structured **defense artifact** (FHIR Claim).

Agent mapping in the story:
- Clinical Reader Agent: extracts patient + evidence from the PDF
- Logic/Coding Agent: selects ICD/CPT codes + confidence/risk
- Auditor Agent: runs the payer policy gate and produces PASS/NEEDS_REVIEW
- Defense Artifact: FHIR `Claim` proposal that the payer can verify/edit

## What we will build (scope)
### 1) Backend: Build a FHIR `Claim` proposal
We will implement a function like: `build_fhir_claim_proposal(...)` that produces a FHIR R4 Claim JSON using our existing state:
- patient: `name` + `DOB/sex` when present (no placeholders)
- provider/organization references (from `organization_id` + payer context)
- diagnosis codes:
  - ICD-11 vs ICD-10 coding system set based on `mapping_path` and extraction metadata
  - use the selected ICD codes from the pipeline output
- procedure/charges:
  - use CPT line items from your existing `financial_summary.line_items`

### 2) Store proposal in the claim payload
When coder submits a claim:
- run policy gate (already done)
- then generate and store:
  - `claim_data.fhir_claim_proposal`
  - keep `claim_data.payer_gate_report` as today for transparency

### 3) Payer UI: Show the FHIR Claim proposal
On the payer adjudication page (`/payer/adjudicate/[id]`) add a section:
- “FHIR Claim Proposal (Hospital Proposed)”
- show a short summary (patient/provider/ICD/CPT)
- include a collapsible JSON viewer for audit/inspection

## Non-goals in this V1.1
- Not implementing full EDI 837 mapping yet
- Not implementing a full payer edits-to-verified-FHIR loop yet
- Not generating EDI 835 yet

## Acceptance criteria (“done” means)
1. After a hospital submits a claim, `claim_data.fhir_claim_proposal` exists in the created DB row. (DONE)
2. The FHIR Claim proposal includes:
   - patient demographics when extracted (DONE)
   - selected ICD codes with correct ICD system context (ICD-11 when WHO path is used) (DONE)
   - CPT procedures/charges from the line items (DONE)
3. The payer UI renders a readable “FHIR Claim Proposal” section without crashing. (DONE)
4. No placeholder DOB/name values are inserted by Integronix when the PDF doesn’t contain them. (DONE)

## Next step after V1.1 (for context)
Once FHIR Claim proposal exists:
- V1.2 will generate **EDI 837 derived from the verified/payer-edited claim**
- V1.3 will generate **EDI 835** from payer decision

## Confirmed decisions (2026-03-20)
1. **EDI 837 timing**: derive only after payer edits/verification (V1.2). The FHIR Claim proposal is the hospital's internal artifact.
2. **ICD system**: always use the ICD system chosen by the hospital (ICD-11 or ICD-10). No internal translation. Payer receives and accepts the hospital's chosen coding system.

