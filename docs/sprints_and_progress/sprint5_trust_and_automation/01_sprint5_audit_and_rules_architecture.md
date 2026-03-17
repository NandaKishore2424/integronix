# Sprint 5: Trust & Automation (Phase 1 & Phase 2)
**Status:** Completed (MVP)
**Focus:** HIPAA Compliance, Immutable Action Auditing, and Deterministic Automated Adjudication.

---

## 1. Architectural Changes Made

To move Integronix from a prototype demonstration into a resilient enterprise platform, we needed to establish trust (who clicked what button) and introduce backend efficiency logic (not every claim needs human review).

We achieved this by building two powerful backend structures and updating our Next.js UI to natively support them.

### Phase 1: The `claim_audit_logs` Ledger
**Goal:** We can no longer rely on `status` and `updated_at`. If an investigation occurs, an Insurance company needs to know exactly *who* at the Hospital submitted the claim, and *who* at the Insurance company approved it.

**How it works:**
1. **Database:** Built `migrations/025_audit_trails.sql`. This creates the `claim_audit_logs` table which acts as an append-only ledger linked to the `claims` table via Foreign Key.
2. **Backend Engine:**
   * Inside `backend/routes/claims.py`, the `POST /api/v1/claims/submit` endpoint now actively injects a row into `claim_audit_logs` stating the claim transitioned from `None` ➜ `SUBMITTED`.
   * The `POST /api/v1/claims/adjudicate/{claim_id}` endpoint injects transition rows (e.g., `SUBMITTED` ➜ `PAID` or `DENIED`), alongside the text justification.
3. **Frontend UI Integration:**
   * **API Client:** Updated the `Claim` type interface in `frontend/src/lib/api.ts` to expect the nested array.
   * **Timeline React Component:** Inside the Payer Desk (`frontend/src/app/payer/adjudicate/[id]/page.tsx`), we mapped the `claim_audit_logs`. We execute a Javascript `.sort()` to order the logs by chronologically increasing `created_at` timestamps, rendering a visual dotted line history at the bottom of the financial panel.

### Phase 2: The Deterministic Payer Rules Engine
**Goal:** Automate simple adjudications to save human labor.

**How it works:**
1. **The Python Service:** We built `backend/services/rules_engine.py`. This exposes an `evaluate_claim(claim_data, patient_name)` function.
2. **Trigger Logistics:** The logic is completely decoupled from the Human UI. It fires automatically inside the `POST /api/v1/claims/submit` pipeline *before* the claim is saved.
3. **Current Active Rules:**
   * **Clinical Danger Check:** If the raw Integronix AI `risk_score` exceeds 85, the claim is auto-denied due to medical coding overcharge risk.
   * **Demographics Check:** Hardcoded fallback rules. For example, if CPT 58150 (Hysterectomy) or CPT 59400 (Obstetrics) occurs, and the patient name parses as male, the claim instantly fails the engine.
4. **Behavior:** If a claim fails the engine natively, it enters the global Payer Inbox directly with `status: DENIED` and an automated `denial_reason` appended to the database and Audit Log. The human Payer Desk UI reflects this immediately, hiding the manual "Approve/Deny" buttons.

---

## 2. Code Location Directory

If future developers need to modify or expand upon Sprint 5, refer to these critical files:

### Database
* Initial Architecture: `migrations/025_audit_trails.sql`

### The Backend
* Rule Logic Engine: `backend/services/rules_engine.py`
* The API Webserver Core: `backend/routes/claims.py` (Lines ~50-90 for Submit, ~250-265 for Adjudicate Ledger execution).

### The Frontend
* The Typed Interfaces: `frontend/src/lib/api.ts`
* The Timeline Render Logic: `frontend/src/app/payer/adjudicate/[id]/page.tsx`

---

## 3. Next Steps (Roadmap)
The platform is fully tracking basic RCM state loops up to the point of Adjudication. The biggest remaining capability gap is the inability for Hospitals to fight back against Denied claims. 

The next phase of work (Sprint 6) should focus entirely on the **Hospital Appeals Flow**, allowing the `APPEALED` status to trigger and unlocking a secondary workflow channel for human-to-human negotiation.
