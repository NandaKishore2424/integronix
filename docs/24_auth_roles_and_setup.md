# 24 — Auth, Roles, Tenant Architecture & Demo Setup

> **Added:** 2026-03-11  
> **Purpose:** Complete reference for multi-tenant structure, user roles, Supabase Auth setup, database changes (migrations 011–017), frontend pages, and hackathon demo flow.

---

## 1. Tenant Architecture — 3 Levels

```
Organization  (top-level tenant)
    └── Branch  (department / wing / campus)
          └── User  (scoped to org + optional branch)
```

Every clinical case, coding result, and audit log is owned by exactly **one organization**. Supabase Row-Level Security (RLS) enforces this at the database level — Hospital A physically cannot query Hospital B's data, even with a valid JWT.

---

## 2. Organizations

Top-level entity. All data is scoped to one organization.

| Column | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `name` | TEXT | e.g. `City General Hospital` |
| `slug` | TEXT | URL-safe, unique — e.g. `city-general-hospital` |
| `type` | TEXT | `hospital` · `clinic` · `rcm_vendor` · `diagnostic_center` |
| `country` | TEXT | Default `US` |
| `timezone` | TEXT | Default `America/New_York` |
| `is_active` | BOOLEAN | Soft-delete flag |

**Demo org seeded:**
- Name: `City General Hospital`
- Slug: `city-general-hospital`
- Type: `hospital`
- ID: `00000000-0000-0000-0000-000000000001`

---

## 3. Branches

A branch is a physical or logical sub-unit of an organization (department, campus, specialty wing). Cases are tracked per branch for analytics and reporting.

| Column | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `organization_id` | UUID | FK → organizations |
| `name` | TEXT | Unique within the org |
| `code` | TEXT | Short internal code e.g. `CGH-CARD` |
| `city` / `state` | TEXT | Location |
| `is_active` | BOOLEAN | Soft-delete |

**Demo branches seeded:**

| ID | Name | Code | City |
|---|---|---|---|
| `...000010` | Main Campus — Cardiology | `CGH-CARD` | New York, NY |
| `...000011` | North Wing — Endocrinology | `CGH-ENDO` | New York, NY |
| `...000012` | South Campus — Orthopaedics | `CGH-ORTH` | New York, NY |

---

## 4. Users & Roles

Each user belongs to one organization and optionally one branch. Branch is `NULL` for org-wide roles.

| Column | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `organization_id` | UUID | FK → organizations |
| `branch_id` | UUID ⬜ | FK → branches (nullable for org-wide users) |
| `email` | TEXT | Unique |
| `full_name` | TEXT | Display name |
| `role` | TEXT | `admin` · `auditor` · `coder` |
| `auth_id` | UUID | FK → `auth.users(id)` — links to Supabase Auth |
| `is_active` | BOOLEAN | Soft-delete |
| `last_login_at` | TIMESTAMPTZ | Updated on sign-in |

### Role Definitions

| Role | What They Can Do | Branch Restriction |
|---|---|---|
| `admin` | Full org access — manage users, view all branches, view all results | ❌ None (org-wide) |
| `auditor` | Read-only across entire org — view all cases, results, audit logs | ❌ None (org-wide) |
| `coder` | Submit clinical cases via AI pipeline, view results from own branch only | ✅ Scoped to `branch_id` |

### Demo Users Seeded

> **Passwords not stored here.** Check `.env.local` for the demo user password, or ask the team lead.

| Email | Full Name | Role | Branch |
|---|---|---|---|
| `admin@citygeneral.demo` | Dr. Sarah Chen (Admin) | `admin` | All branches |
| `auditor@citygeneral.demo` | James Patel (Auditor) | `auditor` | All branches |
| `coder.cardio@citygeneral.demo` | Maria Santos (Coder) | `coder` | Cardiology (`CGH-CARD`) |
| `coder.endo@citygeneral.demo` | Raj Kumar (Coder) | `coder` | Endocrinology (`CGH-ENDO`) |
| `demo@integronix.ai` | Demo User | `admin` | All branches |

> The `demo@integronix.ai` user is triggered by the **Demo Access** button on the login page.  
> Credentials are stored in `.env.local` as `NEXT_PUBLIC_DEMO_EMAIL` and `NEXT_PUBLIC_DEMO_PASSWORD`.

---

## 5. Database Changes — Migrations 011–017

These migrations were added after the initial build (001–010) to implement multi-tenancy.

| Migration | What It Does |
|---|---|
| `011_create_organizations.sql` | Creates `organizations` table with `updated_at` auto-trigger |
| `012_create_branches.sql` | Creates `branches` table with `UNIQUE(organization_id, name)` constraint |
| `013_create_users.sql` | Creates `users` table with `role CHECK` constraint and indexes |
| `014_add_tenant_columns.sql` | Adds `organization_id` + `branch_id` FK columns to `clinical_cases` and `coding_results` |
| `015_row_level_security.sql` | Enables RLS on `clinical_cases`, `coding_results`, `audit_log`; adds `current_user_org_id()` helper function |
| `016_seed_demo_org.sql` | Seeds demo organization, 3 branches, and 4 demo users |
| `017_add_auth_id_to_users.sql` | Adds `auth_id UUID UNIQUE REFERENCES auth.users(id)` to `public.users` + fast lookup index |

### RLS Policy Summary (Migration 015)

The `current_user_org_id()` function reads `organization_id` from the JWT's `app_metadata` and is used in every RLS policy:

```sql
USING (organization_id = current_user_org_id())
```

Applied to: `SELECT`, `INSERT`, `UPDATE` on `clinical_cases`, `coding_results`, `audit_log`.

> **Note:** The backend uses the Supabase `service_role` key which bypasses RLS. This is intentional — the AI pipeline writes results on behalf of the user. The service role key is **never** exposed to the frontend.

### Linking Auth Users to public.users (Post-Setup SQL)

After creating users in Supabase Auth, run this to link them (matches by email automatically):

```sql
UPDATE public.users u
SET auth_id = a.id
FROM auth.users a
WHERE a.email = u.email;
```

---

## 6. Frontend Pages

The frontend is a **Next.js 14 App Router** application.

### Page Map

| Route | File | Description |
|---|---|---|
| `/` | `app/page.tsx` | Landing page — product hero, feature highlights, CTA buttons |
| `/auth/login` | `app/auth/login/page.tsx` | Sign in with email/password + Demo Access button |
| `/auth/signup` | `app/auth/signup/page.tsx` | Register new organisation account |
| `/dashboard` | `app/dashboard/layout.tsx` | Dashboard shell with sidebar navigation |
| `/dashboard/analyze` | `app/dashboard/analyze/page.tsx` | Main AI coding interface (two-tab: Input + Results) |

### Middleware

`src/middleware.ts` — Supabase SSR middleware that:
- Refreshes the Auth session cookie on every request
- Protects `/dashboard/*` routes — redirects unauthenticated users to `/auth/login`
- Redirects already-authenticated users away from `/auth/*` to `/dashboard/analyze`

### Authentication Flow

```
Unauthenticated user visits /dashboard/analyze
    ↓ middleware.ts intercepts
    ↓ No valid session cookie found
    → Redirect to /auth/login

User enters email + password
    ↓ supabase.auth.signInWithPassword()
    ↓ Supabase returns JWT, stored as cookie
    → router.push('/dashboard/analyze')

AuthProvider (global context) fires
    ↓ supabase.auth.getSession()
    ↓ loadProfile(user) — queries public.users by auth_id
    ↓ Then queries organizations by organization_id
    → orgUser + org available globally via useAuth() hook

Coder submits clinical note
    ↓ runCodingPipeline() → POST /api/v1/code/run
    ↓ Backend AI pipeline runs (8 nodes, ~1.5s)
    → Results displayed on Tab 2 (Report)
```

### Component Map

| Component | Purpose |
|---|---|
| `AuthProvider.tsx` | Manages auth state globally — session, orgUser, org, loading, signOut |
| `CodeInputPanel.tsx` | Clinical text input + optional existing ICD code + sample cases |
| `ResultsPanel.tsx` | Orchestrates the results grid across all sub-components |
| `IcdCodeCard.tsx` | Primary recommended ICD code — confidence bar, CC/MCC chips, SNOMED chain |
| `RiskMeter.tsx` | SVG gauge showing risk score + AI confidence |
| `MultiCodeList.tsx` | Primary / secondary / additional codes with scores and rationale |
| `AuditCard.tsx` | Human vs AI side-by-side comparison — discrepancy badge + revenue delta |
| `DrgBadge.tsx` | MCC/CC gap alert with pulsing dot indicator |
| `CandidateChart.tsx` | Recharts horizontal bar chart of all scored candidate codes |
| `FhirPanel.tsx` | Collapsible FHIR R4 Condition JSON with copy-to-clipboard |

---

## 7. Environment Variables

### Frontend (`frontend/.env.local`)

| Key | Description |
|---|---|
| `NEXT_PUBLIC_API_URL` | Backend FastAPI URL (e.g. `http://localhost:8000`) |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon public key |
| `NEXT_PUBLIC_DEMO_EMAIL` | Email for Demo Access button |
| `NEXT_PUBLIC_DEMO_PASSWORD` | Password for Demo Access button |

> Copy `frontend/.env.local.example` → `frontend/.env.local` and fill in values.

### Backend (`backend/.env`)

| Key | Description |
|---|---|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Supabase service role key (bypasses RLS — keep secret) |
| `GROQ_API_KEY` | Groq API key for LLaMA 3.3-70B (clinical extraction) |

---

## 8. Demo Flow (Hackathon Presentation)

### Start servers

```powershell
# Terminal 1 — Backend
cd backend
uvicorn main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend
npm run dev
# → http://localhost:3000
```

### Step-by-step demo

1. Open **http://localhost:3000** → landing page
2. Click **Get Started** → `/auth/login`
3. Click **Demo Access** button (or login with `admin@citygeneral.demo`)
4. On the Analyse page, paste into the clinical text box:
   > *"Patient has Type 2 diabetes mellitus with chronic kidney disease stage 3. eGFR is 42 mL/min. Blood pressure controlled with lisinopril."*
5. In **Existing Code for Review** → type `E11.9`
6. Click **Analyse Documentation**
7. Show judges:
   - **Recommended Code:** `E11.22` (upgraded from `E11.9`)
   - **Revenue Delta:** `+$900` (missed reimbursement recovered)
   - **Discrepancy:** `SPECIFICITY_IMPROVEMENT` — "Higher Specificity Available"
   - **DRG Badge:** `CC_MISSED` — Complication Not Captured
   - **Risk Meter:** `LOW` (AI is confident)
   - **FHIR R4 Panel:** Export-ready for EHR integration
   - **Candidate Chart:** Shows all scored ICD candidates

### Key talking points for judges

- **No LLM hallucination in code selection** — deterministic 7-step scoring algorithm
- **Hybrid pipeline** — SNOMED → ICD crosswalk (direct) → vector embedding fallback
- **HIPAA-ready** — RLS isolates each hospital's data at DB level
- **Multi-tenant** — one platform, many hospitals, branch-level analytics
- **FHIR R4** — enterprise interoperability built-in, not bolted-on
