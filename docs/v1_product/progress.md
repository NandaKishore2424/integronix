# V1 Progress Log

## Done (current)
- WHO ICD-11 lookup + caching into local `icd_codes` works (WHO API v2 → local cache).
- ICD-11 strings can persist in `coding_results` (dropped `coding_results.ai_icd_code` FK).
- Fixed EDI export crash by removing dependency on `organizations.address` in the export query.
- Frontend currency display standardized (no mixed `$` + `₹`).
- Removed broken payer navigation (`/payer/adjudicate` base route) and routed users safely to the correct pages.
- Patient identity flow hardened:
  - Stop using placeholder DOB/name values when missing.
  - Extract and pass `patient_sex` end-to-end (required for payer policy checks).
- FHIR Claim Proposal working end-to-end:
  - Backend builds a hospital-proposed FHIR R4 `Claim` and stores it in `claim_data.fhir_claim_proposal`
  - Payer adjudication UI renders “FHIR Claim Proposal” including ICD system context (ICD-11/ICD-10) + CPT line items
  - CPT codes now populate correctly in FHIR `Claim.item[].productOrService` (code-key fallback fix)

## Done (payer trust + automation)
- Added payer-configurable auto-approve policy fields to `public.payers` (migration `015_payer_auto_approve_policies.sql`).
- Implemented `services/payer_policy_gate.py`:
  - deterministic “trust gate” checks (DOB/sex presence, ICD system compatibility, mapping quality, confidence + risk thresholds)
  - returns a detailed `payer_gate_report` with reasons (for transparency).
- Updated `POST /api/v1/claims/submit`:
  - runs the policy gate
  - stores `payer_gate_report` into `claim_data`
  - if `auto_approve_enabled=true` and gate `PASS`, sets claim status automatically (PAID/PARTIALLY_PAID using configured responsibility %)
- Updated payer adjudication UI to show the `Payer Policy Gate` section with reasons and “auto-decision enabled” context.
- Updated payer inbox UI to show `PARTIALLY_PAID` claims (default demo UX uses `ALL`).

## Stability fixes applied during V1
- Fixed a backend crash during policy gate evaluation (converted Supabase “single row response” into a dict before calling the gate).
- Removed coder UI noise/404s by no longer calling the fragile `/payers/by-org/{orgId}` name-matching endpoint for payer dropdown resolution.

## Implementing next
- (Next) Replace the current EDI flow with a real EDI 837 derived from the payer-verified/edited claim (V1.2).
- Add payer edit workflow:
  - payer selects/edits codes
  - we store `payer_verified` output + payer reasons
- Add payer edit workflow:
  - payer selects/edits codes
  - we store `payer_verified` output + payer reasons
- (Later) Generate EDI 835 (remittance/denial) from payer decision.

