# Architecture Notes (V1)

## Key domain objects
- **Hospital PDF Upload**
  - input: de-identified or raw discharge summary
  - output: structured clinical entities + patient demographics (if documented)
- **Coding Proposal (Hospital proposed)**
  - proposed ICD codes (ICD-11 via WHO when enabled, otherwise ICD-10 fallback)
  - proposed procedure codes (CPT/procedures)
  - evidence snippets + provenance (WHO/local/embedding/provider)
  - validation report: `PASS` / `NEEDS_REVIEW` with reasons
- **FHIR Claim Proposal**
  - internal interchange format for downstream analytics / integration
- **EDI 837 Claim (Export)**
  - derived from the verified/final code set for payer interchange
- **Payer Policy Gate**
  - input: coding proposal + payer configuration (accepted ICD version, required demographics, confidence/risk thresholds)
  - output: `AUTO_APPROVE` or `NEEDS_REVIEW` with detailed reasons
- **Payer Verified Output**
  - payer can accept or edit codes
  - output stored with payer reasons
  - remittance/denial: **EDI 835** (later phase; may be simplified in V1)

## Data flow
1. Hospital uploads PDF
2. Integronix extracts + proposes codes
3. Integronix generates proposal payload (FHIR internal + validation report)
4. Hospital submits “proposal to payer” (EDI 837 derived; for now EDI export is simplified)
   - In V1 we run a deterministic **Payer Policy Gate** before submission is finalized
   - If payer enables auto-approve and gate `PASS`, claim status auto-updates (PAID / PARTIALLY_PAID)
5. Payer applies policy/edits and finalizes (or reviews auto-approved items)
6. Payer returns EDI 835 (later phase)

## What “trustable” means in practice
- Payer must see:
  - required demographics status (DOB/sex present or missing)
  - ICD version compatibility
  - mapping quality signals (direct WHO vs embedding failed)
  - confidence + risk thresholds
- Auto-approve is **never silent**:
  - always show the rule reasons that caused the decision

