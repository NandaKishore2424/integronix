# Sprint 4: Enterprise Frontend Architecture & Payer Portal

**Goal:** Transform the monolithic `/dashboard` Next.js application into a modular, highly scalable, and role-based ecosystem (Hospital vs. Payer). Ensure seamless page flow, unbroken imports (leveraging `@` aliases), and robust layout-level authorization.

---

## 1. Architectural Vision (Senior Frontend Engineer Perspective)

An industry-standard enterprise B2B platform like Integronix requires **Tenant Segregation** at the routing level. A Medical Coder at a hospital should never accidentally stumble into the Payer adjudication screens, and Vice Versa.

We will achieve this using **Next.js App Router Sub-Trees**. By giving each persona its own root folder, we can assign distinct `layout.tsx` files. This means:
*   **Unique Sidebars:** The Payer portal gets a blue/green theme with "Claims Inbox" & "Policy Rules". The Hospital portal gets "Coding Analysis" & "Patient Revenue".
*   **Scoped Middleware/Auth:** We can wrap `/hospital` and `/payer` in separate authorization guards.
*   **Scalability:** When we add "Auditors" or "Patients" next year, they just get a new root folder (`/auditor`, `/patient`).

### Target Directory Structure
```text
frontend/src/app/
├── (auth)/                          # Route Group: Keeps URL clean (/login, /signup)
│   ├── login/page.tsx
│   └── signup/page.tsx
├── hospital/                        # 🏥 THE PROVIDER PORTAL
│   ├── layout.tsx                   # Hospital-specific Navigation & Auth Guard
│   ├── coder/                       # Role: Medical Coders
│   │   ├── analyze/page.tsx         # (Moved from /dashboard/analyze)
│   │   └── history/page.tsx         # (Moved from /dashboard/cases)
│   ├── rcm/                         # Role: Billing & Revenue Staff
│   │   ├── inbox/page.tsx           # (Moved from /dashboard/claims)
│   │   └── analytics/page.tsx       # (Moved from /dashboard/analytics)
│   └── admin/                       # Role: Organization Admins
│       ├── users/page.tsx           # (Moved from /dashboard/users)
│       └── branches/page.tsx        # (Moved from /dashboard/branches)
└── payer/                           # 🏢 THE INSURANCE PORTAL
    ├── layout.tsx                   # Payer-specific Navigation & Auth Guard (Different Theme)
    ├── inbox/page.tsx               # NEW: See incoming claims from hospitals
    └── adjudicate/[id]/page.tsx     # NEW: Detailed screen to approve/deny
```

---

## 2. Migration Strategy (Zero-Downtime / No Broken Links)

To ensure we don't break the application while moving files, we will follow a strict execution order.

### Step 1: Prepare the Layouts & Auth Guards
1.  Create `src/app/hospital/layout.tsx`. 
    *   *Implementation:* Duplicate the current `dashboard/layout.tsx`, but modify the `navItems` to specifically cater to the Hospital (grouping links logically by Coder, RCM, and Admin).
2.  Create `src/app/payer/layout.tsx`.
    *   *Implementation:* Build a brand new sidebar, styled slightly differently (e.g., green accents instead of indigo) to visually differentiate the Payer context. Navigation includes "Global Claims Queue" and "Adjudication History".

### Step 2: Safe File Relocation (Leveraging Absolute Imports)
Because the codebase strictly uses TypeScript path aliases (`@/components/...`, `@/lib/api`), moving the `page.tsx` files across directories **will not break component imports**. 

We will move the folders exactly as mapped above:
*   `mv src/app/dashboard/analyze src/app/hospital/coder/analyze`
*   `mv src/app/dashboard/cases src/app/hospital/coder/history`
*   *...and so forth.*

### Step 3: Fixing Internal Breadcrumbs & Link Tags
*Risk:* While `@/components` imports won't break, native `<Link href="...">` or `router.push(...)` calls *will* break if they reference the old `/dashboard` paths.
*   *Action:* Perform a global Find & Replace across the `src` directory:
    *   `/dashboard/analyze` ➡️ `/hospital/coder/analyze`
    *   `/dashboard/claims` ➡️ `/hospital/rcm/inbox`
    *   `/dashboard/cases` ➡️ `/hospital/coder/history`

### Step 4: The Login Redirect Logic Setup
Currently, `login/page.tsx` pushes users to `/dashboard/analyze` upon success. 
*   *Action:* Update `login/page.tsx` so that if the user's organization is a Hospital, they route to `/hospital/coder/analyze`. If their organization is a Payer (like Star Health), they route to `/payer/inbox`. (For this demo, we will provide a simple UI toggle or logic to route the user gracefully).

---

## 3. Developing the New Payer Portal Features

Once the migration safely anchors the existing Hospital features, we will build out the missing Payer features to complete the RCM loop.

*   **Payer Inbox (`/payer/inbox`):** 
    *   A dashboard that calls a new backend endpoint: `GET /api/v1/claims/payer/{payer_id}`.
    *   Displays a queue of claims submitted by all hospitals, showing Status `SUBMITTED`, Requested Billed Amount, and Risk Flag.
*   **Adjudication Review (`/payer/adjudicate/[id]`):**
    *   A detailed layout where the Payer agent sees the exact ICD/CPT codes and the Hospital's AI-generated evidence.
    *   Includes a control panel to click **"Approve (Pay Contract Rate)"** or **"Deny (Manual Edit)"**.
    *   *Action:* Hooks entirely into the `POST /api/v1/claims/adjudicate/{claim_id}` backend engine we built in Sprint 3.

---

## 4. Final Verification
*   Execute `pnpm run build` after the file migration to let the TypeScript compiler catch any straggling relative imports or broken `<Link>` tags.
*   Ensure the UX is seamless: A hospital coder submits a claim, logs out, logs in as a Star Health Payer agent, sees the claim pop up in the Payer queue, and adjudicates it. Loop Closed.

---

## 5. Status & Completion Log (Post-Sprint 4)

✅ **Sprint 4 is 100% Complete.**
* The frontend monolith has been completely segregated into `/hospital` and `/payer` Next.js sub-trees.
* Path imports worked seamlessly, and broken direct URL links were regex-replaced.
* `pnpm run build` succeeds perfectly with 0 type errors.
* The Payer Adjudication Queue and Review Desk are fully integrated with the FastAPI backend.

### What Else Are We Missing? (The "Feature Gaps")
While the end-to-end RCM loop is technically functional today (Hospital codes -> Hospital Submits -> Payer Adjudicates), an enterprise-grade platform needs these key features before hitting a "v1.0 Production" state.

Below is the detailed Product Manager's Roadmap for the upcoming Sprints to close these gaps.

---

## 🚀 Sprint 5: Trust & Automation (Core Infrastructure)
**Theme:** Making the system unaccountably resilient and reducing human labor at the Payer level.

### Feature 5.1: HIPAA Audit Trails (Immutable Logging)
*   **User Story:** "As a Compliance Officer, I need an immutable log of who changed a claim's status and when, so we can pass our SOC2 and HIPAA audits."
*   **Product Plan:** We cannot rely solely on the `claims.updated_at` timestamp. We need a historical ledger of every state mutation.
*   **Technical Implementation:**
    *   **DB Migration (`025_audit_trails.sql`):** Create a `claim_audit_logs` table `(id, claim_id, previous_status, new_status, changed_by_user_id, timestamp, action_notes)`.
    *   **Backend (`routes/claims.py`):** Update the `submit_claim` and `adjudicate_claim` endpoints to `INSERT` a row into `claim_audit_logs` every time a status changes.
    *   **Frontend (`app/payer/adjudicate/[id]/page.tsx` & `app/hospital/coder/history/[id]/page.tsx`):** Add a "Timeline" or "History" component rendering this audit trail vertically.

### Feature 5.2: Automated Payer Rules Engine (Level 1)
*   **User Story:** "As an Insurance Claims Adjuster, I want the system to auto-deny claims that obviously violate bundling rules or lack matching diagnoses, so I only have to manually review complex cases."
*   **Product Plan:** Build a deterministic rules engine that fires *before* a claim hits the human review queue.
*   **Technical Implementation:**
    *   **Backend (`services/rules_engine.py`):** Create a service that accepts a claim payload. It will evaluate Demographic Checks (e.g., mismatching gender CPTs) and Clinical Necessity (AI Confidence > 85).
    *   **Backend (`routes/claims.py`):** The `/submit` endpoint will synchronously pass the claim through the `rules_engine`. Claims failing the engine instantly change to `status: DENIED` with an automated `denial_reason` before reaching the human Inbox.

---

## 🚀 Sprint 6: The Appeals Workflow & Clearinghouse Sync
**Theme:** Allowing hospitals to fight back against denials and allowing our system to talk to legacy bank/clearinghouse networks.

### Feature 6.1: The Hospital Appeals Flow
*   **User Story:** "As a Medical Biller at a Hospital, I want to click 'Appeal' on a denied claim, attach a doctor's addendum, and send it back to the Payer for a secondary review."
*   **Product Plan:** Denied claims need to be resurrected into a new conversational state rather than sitting dead in the void.
*   **Technical Implementation:**
    *   **DB Schema:** Add a new status `APPEALED` to the `status` ENUM in the `claims` table.
    *   **Backend (`routes/claims.py`):** Create `POST /api/v1/claims/{id}/appeal` accepting an `appeal_justification` payload.
    *   **Frontend (`app/hospital/rcm/claims/page.tsx`):** Add a new Tab for "Denied / Action Required".
    *   **Frontend (`app/hospital/rcm/claims/[id]/page.tsx`):** Build a dedicated detail view for RCM staff to view the denial reason, formulate an argument, and hit "Submit Appeal".

### Feature 6.2: EDI 837 Export (Interoperability Magic)
*   **User Story:** "As a Payer Data Engineer, I want the system to automatically generate an X12 (EDI 837) formatted text file for approved claims so we can integrate them with our legacy mainframe."
*   **Product Plan:** Medical claims must ultimately conform to EDI formats. We must map our clean SQL data into the standard pipelined EDI 837 format.
*   **Technical Implementation:**
    *   **Backend (`services/edi_generator.py`):** Python parser translating our DB schema into standard segments (`ISA`, `GS`, `ST`, `CLM`).
    *   **Backend (`routes/export.py`):** Endpoint `GET /api/v1/export/edi/837/{claim_id}` that returns a raw `.txt` file.
    *   **Frontend (`app/payer/inbox/page.tsx`):** Add an "Export EDI" button next to `PAID` claims.

---

## 🚀 Sprint 7: Payer Analytics & Organization Admin
**Theme:** Giving Payers the same level of analytical insight that Hospitals have, and polishing the platform infrastructure.

### Feature 7.1: Payer Financial Analytics
*   **User Story:** "As a Payer Executive, I want a dashboard showing my total financial payout liability for the month, and identifying which hospitals submit the highest risk-scored claims."
*   **Technical Implementation:**
    *   **Backend (`routes/payer_analytics.py`):** Endpoints that aggregate `total_paid_amount` categorized by month, and `avg(risk_score) GROUP BY organization_id`.
    *   **Frontend (`app/payer/analytics/page.tsx`):** A Tremor/Recharts dashboard. Add the chart icon to the `payer/layout.tsx` sidebar.

### Feature 7.2: Payer Staff Management
*   **User Story:** "As a Payer Admin, I want to invite, suspend, and manage staff accounts acting as Adjudicators."
*   **Technical Implementation:**
    *   **Frontend (`app/payer/admin/users/page.tsx`):** Build the data table mimicking the hospital's admin view, but utilizing a Payer-scoped backend query `GET /api/v1/admin/payer/users`.
