# 🐛 Bugs Found & Fixed — E2E Testing Session

**Date:** 17–18 March 2026  
**Session:** Sprint 7 E2E Manual Testing  
**Testers:** Nanda Kishore (coder), Subashini (RCM), Nathin (payer)

---

## Bug 1 — `403 Forbidden` on RCM Login

### What Happened
When logging in as **Subashini** (role: `rcm`), the app would redirect to the `403 Forbidden` page instead of the Claims Inbox.

### Root Cause
Three separate issues, all related to role-based routing:

1. **`middleware.ts`** — A hardcoded redirect sent every logged-in user visiting `/auth/*` to `/hospital/coder/analyze`, regardless of their role. So `rcm` users ended up on a coder page, hit the RBAC check, and got bounced to `/403`.
2. **`403/page.tsx`** — The fallback "Go to your dashboard" button for `rcm` users pointed to `/hospital/rcm/claims` (which doesn't exist) instead of `/hospital/rcm/inbox`.
3. **`login/page.tsx`** — After login, all non-payer users were routed to `/hospital/coder/analyze`, ignoring the `rcm` role entirely. Also the Supabase query was matching by `id` instead of `auth_id`.

### Fix
- **`middleware.ts`**: Changed the `/auth/*` redirect to be role-aware — payer → `/payer/inbox`, rcm → `/hospital/rcm/inbox`, others → `/hospital/coder/analyze`.
- **`403/page.tsx`**: Corrected the RCM redirect URL to `/hospital/rcm/inbox`.
- **`login/page.tsx`**: Added role check after login using `auth_id` column; routing now handles `payer`, `rcm`, and default `coder/admin` correctly.

---

## Bug 2 — `500 Internal Server Error` on Claims Inbox Load

### What Happened
When Subashini navigated to `/hospital/rcm/inbox`, the page failed with a `500 Internal Server Error`. Backend terminal showed:
```
supabase._sync.client.SupabaseException: supabase_url is required
```

### Root Cause
`routes/claims.py` used `os.getenv("SUPABASE_URL", "")` and `os.getenv("SUPABASE_SERVICE_KEY", "")` directly. Since `python-dotenv` was not explicitly called in `main.py`, these returned empty strings at runtime. The rest of the backend uses a centralized `settings` object from `config.py` (powered by `pydantic-settings`) which correctly loads the `.env` file.

### Fix
Replaced raw `os.getenv()` calls with `settings.supabase_url` and `settings.supabase_service_key` from `config.py`. This ensures the credentials are always loaded properly.

**File Changed:** `backend/routes/claims.py`

---

## Bug 3 — Claim Submission Fails with Foreign Key Violation

### What Happened
Clicking **Submit Claim** as Nanda showed the error:
```
insert or update on table "claims" violates foreign key constraint "claims_organization_id_fkey"
```
The payload showed `organization_id: "00000000-0000-0000-0000-000000000001"` — the old City General Hospital UUID.

### Root Cause
`ResultsPanel.tsx` had a hardcoded default for the `orgId` prop:
```tsx
export default function ResultsPanel({ result, onReanalyze, orgId = '00000000-0000-0000-0000-000000000001' })
```
Both `analyze/page.tsx` and `history/[session_id]/page.tsx` were not passing the `orgId` prop, so the hardcoded fallback was used. The database only has Saveetha Hospitals (`f2a96996-...`), so the FK check failed.

### Fix
- **`ResultsPanel.tsx`**: Removed the hardcoded default UUID.
- **`analyze/page.tsx`**: Already had `orgId` from `useAuth()` — just needed to pass it as `orgId={orgId ?? undefined}`.
- **`history/[session_id]/page.tsx`**: Added `useAuth()` import, extracted `orgId`, and passed it to `ResultsPanel`.

---

## Bug 4 — Adjudication Page Shows `404 Not Found`

### What Happened
Clicking **Review Case** on a claim in Nathin's inbox navigated to `/payer/adjudicate/<claim_id>` and showed a blank 404 page.

### Root Cause
The Next.js dev server had started before the `payer/adjudicate/[id]/` folder existed (or was newly created). Next.js caches its route manifest at startup and doesn't always pick up new dynamic route folders without a restart.

### Fix
Restarted the `pnpm run dev` process. Next.js then compiled the `/payer/adjudicate/[id]` route correctly. No code changes were needed.

---

## Bug 5 — All Claim Amounts Show `$0`

### What Happened
After adjudicating a claim as Nathin:
- Hospital Billed: `+$0`
- Payer Allowed: `+$0`
- Payer Responsibility (80%): `+$0`
- Patient Owes (20%): `+$0`

### Root Cause — Two-Part

**Part A — Backend: `financial_calculator.py`**  
When the AI pipeline finds no CPT procedure codes (e.g., for a pure diagnosis visit like J96.00), the financial calculator returned `total_estimated_revenue: 0` instead of falling back to ICD code reimbursement values.

Also, the same `os.getenv()` bug (see Bug 2) was present here too — the Supabase client used to fetch the pricing multiplier was being initialized with empty credentials, silently falling back to multiplier `1.0`.

**Part B — Frontend: `ResultsPanel.tsx`**  
The claim submit payload set `total_billed_amount` from `result.financial_summary?.total_estimated_revenue ?? 0`. When that value was `0`, the backend adjudication computed `0 × 80% = $0` for everything.

### Fix
- **`backend/agents/financial_calculator.py`**:
  - Replaced `os.getenv()` with `settings.supabase_url / settings.supabase_service_key`.
  - When no CPT codes exist, now sums ICD code `base_reimbursement` values as a fallback so the claim always has a non-zero billed amount.
- **`frontend/src/components/ResultsPanel.tsx`**:
  - Added fallback logic: prefers CPT-based revenue, falls back to ICD `base_reimbursement` sum when CPT revenue is 0.

---

## Bug 6 — Payer Inbox Ignores Selected Payer; Always Shows First Payer's Claims

### What Happened
When Nathin (Global Health Insurance) logged in, the Claims Queue showed all claims regardless of which payer was selected during submission. The inbox hardcoded `payers[0]` — the first payer alphabetically in the database.

This meant the payer filter during claim submission was cosmetic — it had no impact on which inbox would receive the claim.

### Root Cause
`payer/inbox/page.tsx` called `fetchPayers()` and used `payers[0].id` regardless of the logged-in user. The `payers` table has no `organization_id` column, so there was no link between Nathin's organization and the "Global Health Insurance" payer record.

### Fix — Three-Part

1. **New backend endpoint** `GET /api/v1/claims/payers/by-org/{org_id}`:
   - Looks up the org's `name` from the `organizations` table.
   - Finds the `payers` record whose `name` matches via `ILIKE`.
   - Returns the correct payer for the logged-in user's org.

2. **`frontend/src/lib/api.ts`**: Added `fetchPayerByOrg(orgId)` function.

3. **`frontend/src/app/payer/inbox/page.tsx`**:
   - Imported `useAuth` to get `orgUser.organization_id`.
   - Replaced `payers[0]` with `fetchPayerByOrg(orgUser.organization_id)`.
   - The inbox now loads only claims submitted to the payer that matches the logged-in user's organization.

---

## Summary Table

| # | Bug | Severity | Area | Status |
|---|-----|----------|------|--------|
| 1 | RCM role gets 403 on login | 🔴 Critical | Auth / Middleware | ✅ Fixed |
| 2 | Claims inbox returns 500 (missing Supabase URL) | 🔴 Critical | Backend — `claims.py` | ✅ Fixed |
| 3 | Claim submit fails with FK violation (City General UUID) | 🔴 Critical | Frontend — `ResultsPanel.tsx` | ✅ Fixed |
| 4 | Adjudication page shows 404 | 🟡 Medium | Next.js route cache | ✅ Fixed (restart) |
| 5 | All claim amounts show $0 | 🟡 Medium | Backend + Frontend financial logic | ✅ Fixed |
| 6 | Payer inbox ignores actual payer selection | 🟡 Medium | Frontend inbox + missing API endpoint | ✅ Fixed |
