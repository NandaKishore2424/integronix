# V1 Product (Hospital + Payer Trust)

This folder tracks the V1 “real application” direction for the Integronix Hackathon project.

## What V1 means
- Integronix acts as a **hospital-side coding assistant**:
  - Extracts clinical entities from hospital PDF
  - Proposes ICD codes + procedure codes with evidence + provenance
  - Generates a **FHIR Claim proposal** for internal hospital analysis
  - Exports an **EDI 837 claim** to send to the payer
- Payers keep their own adjudication logic:
  - Payer applies **policy/edits** + optional human review
  - Payer can **edit codes** and must provide reasons
  - Payer returns **EDI 835** (remittance/denial response)

## Trust promise (must-haves)
1. **Transparency**: payer can see why AI recommended codes.
2. **Deterministic rules**: auto-approve only when payer policy says it’s safe.
3. **Auditability**: store both hospital proposal and payer verified output.

## Current status
- PDF → ICD-11 via WHO API path works and stores ICD codes.
- “Coder submit claim → payer adjudicate” flow works (trust simulation).
- Implemented V1 “payer trust gate”:
  - deterministic policy checks
  - detailed `payer_gate_report` with reasons
  - payer-configurable auto-approve (PAID / PARTIALLY_PAID)
- Patient identity flow hardened (extract/pass `patient_sex`; stop inventing DOB/name).
- Payer UX improvements:
  - payer inbox displays `PARTIALLY_PAID`
  - payer adjudication page shows the policy gate reasons
- Remaining work:
  - generate a real FHIR `Claim` proposal + derive true EDI 837 from verified output
  - implement payer edit workflow (store payer verified codes + reasons)
  - generate EDI 835 later phase

