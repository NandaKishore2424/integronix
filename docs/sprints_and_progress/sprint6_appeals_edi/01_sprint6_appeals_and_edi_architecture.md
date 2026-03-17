# Sprint 6: Appeals & Interoperability
**Status:** Completed
**Focus:** Hospital Appeals Workflow and EDI X12 Export formatting.

---

## 1. Architectural Additions

In Sprint 5, we introduced automated payer Denials via the Rules Engine. In Sprint 6, we closed the Revenue Cycle loop by allowing Hospitals to dispute those Denials, and finally mapped our bespoke database structures into industry-standard interoperability files.

### Phase 1: The Appeals Architecture
**Goal:** Prevent revenue leakage by giving Hospital Billers an interface and backend route to challenge `DENIED` or `PARTIALLY_PAID` claims.

**How it works:**
1. **Database Foundation:** We utilized the `APPEALED` string flag inside the PostgreSQL `claims` enum that was established in Sprint 5 Migration `025`.
2. **Backend Engine:**
   * Inside `backend/routes/claims.py`, we created `POST /api/v1/claims/appeal/{claim_id}`.
   * This endpoint explicitly guards against appealing a claim that is already `PAID` or `SUBMITTED`.
   * It transitions the claim to `APPEALED`, but *preserves* the original `denial_reason` on the record so context isn't lost.
   * Crucially, the endpoint pushes an immutable history row into the `claim_audit_logs` containing the human-typed "justification" text, proving who submitted the appeal and why.
3. **Frontend Integration:**
   * Updated `frontend/src/lib/api.ts` with `appealClaim` and `exportEdiUrl` proxies.
   * Overhauled `frontend/src/app/hospital/rcm/inbox/page.tsx`. Added a dynamic Action column logic. If a claim is denied, an indigo "Appeal" button triggers a darkened modal overlay capturing the biller's justification text before firing it to our new python service.

### Phase 2: EDI X12 837 Export Generation
**Goal:** Prove the platform can communicate with legacy American healthcare architectures (Clearinghouses) via strict text-based standards.

**How it works:**
1. **The Python Formatter:**
   * Built `GET /api/v1/claims/export/edi/{claim_id}` returning a `PlainTextResponse`.
   * The endpoint queries the full depth of a claim (joining the `organizations` table for NPI/addresses and the `payers` table).
   * It maps the JSON into the **ANSI ASC X12 EDI 837** format. Lines generated include the `ISA/GS` interchange envelopes, the `NM1` provider/payer segments, and loops exactly over the `claim_data.financial_summary.line_items` to insert `SV1` (Service Line) CPT codes.
2. **Frontend UI Integration:**
   * Injected a "Download" lucide icon into every claim row. Because the endpoint returns raw `text/plain` MIME types, clicking it instantly opens/downloads the `.txt` legacy file locally.

---

## 2. Code Location Directory

If future developers need to modify or expand upon Sprint 6, refer to these critical files:

### The Backend
* Appeals Logic & EDI Generator: `backend/routes/claims.py` (Lines ~275-390).

### The Frontend
* The Typed Interfaces: `frontend/src/lib/api.ts`
* The Hospital Inbox Modal UI: `frontend/src/app/hospital/rcm/inbox/page.tsx`

---

## 3. Next Steps (Roadmap)
The core backend Revenue Cycle workflow (Coding -> Submission -> Auto-Denial -> Audit Logging -> Appeals -> Clearance Export) is practically complete for MVP.

However, the UI folder structure relies on "Honor System" routing. A user can freely look at `/hospital/coder`, `/hospital/rcm`, and jump to `/payer` by just typing the URL.

The next major enterprise phase (Sprint 7) requires integrating **Supabase Authentication and Role-Based Access Control (RBAC)** to cryptographically lock Medical Coders out of Billing, and lock Billers out of the Insurance Payer dashboard.
