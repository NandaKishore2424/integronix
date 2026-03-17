# Sprint 3: Payer Integration & Claim Workflow

**Goal:** Turn static coding results into actionable "Claims" that can be submitted to Payers, tracked for status, and adjudicated (Approved/Paid).

## Phase 1: The Claim Engine (Database & API)
- [x] Create the `claims` table to link `clinical_cases` and `billing_results` to Payers.
- [x] Implement a `POST /api/v1/claims/submit` endpoint that takes a coding result and freezes it into a "Filed Claim".
- [x] Add a `status` field to claims: `DRAFT`, `SUBMITTED`, `ADJUDICATING`, `PAID`, `DENIED`.

> **Phase 1 Implementation Notes (Senior Database & Data Engineer Log):**
> * **Schema Engineering:** Engineered a robust `claims` and `payers` relationship in `024_payer_system.sql`. Handles all edge cases including partial payments, patient financial responsibility modeling, and denial reasons.
> * **Data Integrity:** Added Row Level Security (RLS) to ensure users can only ever access claims tied strictly to their `organization_id`.
> * **State Management:** Built `backend/routes/claims.py` providing endpoints that transactionally freeze the entire state (`claim_data` JSONB payload) at the exact moment of submission, maintaining immutable historical audit trails even if the CPT prices change later.

## Phase 2: Payer Adjudication & "Allowed Amounts"
- [x] Implement a simple "Payer Adjudication" module.
- [x] Payers tell us their "Allowed Amount" (e.g., Hospital charges $1,000, Payer allows $800).
- [x] Calculate the **Contractual Adjustment** and **Patient Responsibility**.

> **Phase 2 Implementation Notes (Senior Data Engineer Log):**
> * **Financial Algorithim:** Built `POST /api/v1/claims/adjudicate/{claim_id}`. This acts as our "Simulated Payer Core". It reads the frozen base prices from the claim payload and applies the custom Payer Multiplier (e.g., Medicare = 1.0, Commercial = 1.25) to arrive at the Allowed Amount.
> * **RCM Flow Checks:** Added business logic to ensure the payer never "allows" more than what the hospital actually billed, mirroring a real-world contractual ceiling constraint.
> * **Patient Liability:** Computes exact fractional splits (e.g. 80% Payer / 20% Patient) to arrive at the final metrics needed for the frontend RCM dashboards.

## Phase 3: RCM Frontend (Hospital & Payer Views)
- [x] **Hospital View:** Add a "Submit to Payer" button in the `ResultsPanel`.
- [x] **Claim Tracking:** Add a "Claims Inbox" page where hospitals can see if they've been paid.
- [x] **Payer Mock:** Add a simple "Payer Portal" toggle to demonstrate the Payer approving a claim.

> **Phase 3 Implementation Notes (Senior UI/UX Engineer Log):**
> * **Submission UI:** Upgraded `ResultsPanel.tsx` with a dynamic Payer Dropdown and simulated "Submit Claim" workflow that fires a POST request to freeze the case.
> * **Inbox Component:** Built `ClaimsInboxPage` in `app/dashboard/claims/page.tsx`, offering a high-density tabular view of financial lifecycles (Billed vs Allowed vs Paid vs Patient Responsibility).
> * **Navigation Elements:** Placed the Claims Inbox permanently in the main global `Sidebar` so users conceptually understand the flow from Analysis ➡️ Claims.

---

> [!TIP]
> This sprint is the "Closing of the Loop." It moves our tech from "AI that finds codes" to "An RCM Platform that gets hospitals paid."

**Sprint 3 Status:** ✅ COMPLETED
**Next Steps:** Proceed to Sprint 4 (Optional Payer Portal Demo UI or Final Deployment Polish).
