# Authentication, Roles, & Multi-Tenant Architecture

This document provides a comprehensive reference for Integronix's multi-tenant structure, user roles, and how they bridge with Supabase Authentication.

## 1. Architectural Overview

Integronix uses a **3-tier organizational model** to strictly isolate and compartmentalize data across different clients and their facilities. 

```
Organization  (Level 1 - The Client: e.g., Apollo Hospitals Group)
    └── Branch  (Level 2 - The Facility: e.g., Main Cardiology Wing, Chennai)
          └── User  (Level 3 - The Individual: Doctors, Coders, Admins)
```

**Core Principle:** Every single piece of transaction data (cases, coding results, audit logs) is permanently stamped with an `organization_id` and, where applicable, a `branch_id` and `submitted_by` (User ID).

This is enforced at the database level using PostgreSQL Row-Level Security (RLS) policies within Supabase. It is fundamentally impossible for User A at Hospital A to query or perceive data belonging to Hospital B, regardless of API flaws or direct database requests.

---

## 2. The Core Tables

These tables establish the multi-tenant foundation. See the `migrations/schema/002_core_tables.sql` for the raw definitions.

### `organizations`
The supreme tenant record. Everything rolls up to this table.
- `id`: UUID (Primary Key)
- `name`: Human-readable name.
- `slug`: URL-safe, unique identifier (e.g., `apollo-hospitals`).
- `type`: Categorizes the organization (`hospital`, `clinic`, `rcm_vendor`, `diagnostic_center`, `insurance_payer`).

### `branches`
Logical or physical sub-units within an organization to allow for granular reporting and access control.
- `id`: UUID (Primary Key)
- `organization_id`: UUID (Foreign Key → `organizations(id)`)
- `code`: Internal reference code (e.g., `APO-CHE-CARDIO`).

### `users`
Represents individuals working within the platform.
- `id`: UUID (Primary Key - used internally as `submitted_by`).
- `organization_id`: UUID (Foreign Key → `organizations(id)`). **Every user must belong to an organization.**
- `branch_id`: UUID (Foreign Key → `branches(id)`). **Nullable**. If a user has a specific branch assigned, their access is scoped to that branch. If null, their scope is defined by their role (typically org-wide).
- `auth_id`: UUID (Foreign Key). This is the crucial link to the Supabase `auth.users` table, bridging our application logic with the authentication provider.
- `email`, `role`: User attributes.

---

## 3. Role-Based Access Control (RBAC)

The `role` column in the `users` table determines the permission level. The platform enforces 5 distinct roles:

| Role | Scope | Capabilities | Use Case |
| :--- | :--- | :--- | :--- |
| **`admin`** | Organization-wide | Full access to all branches, cases, and settings within the org. Can manage other users. | IT Admin, Medical Director |
| **`auditor`** | Organization-wide | Read-only access across the entire organization. Can view cases, coding results, and audit logs. Cannot submit new cases. | Compliance Officer, Quality Assurance |
| **`coder`** | Branch-specific | Can submit new clinical cases to the AI pipeline and view results *only* for the branch they are assigned to (`branch_id`). | Medical Coder, Floor Nurse |
| **`rcm`** | Organization-wide | Dedicated to the Revenue Cycle Management module. Manages claims, billing pipelines, and financial analytics. | Billing Specialist, Finance Team |
| **`payer`** | Organization-wide | Restricted access to a specific `/payer/*` portal. Used by insurance adjudicators to review claims submitted by the hospital. | Insurance Partner |

---

## 4. The Auth Flow (Supabase Integration)

Integronix delegates authentication (passwords, JWTs, sessions) to Supabase Auth, but maintains authorization (roles, tenants) in our custom `public.users` table.

1. **User Sign-Up/Creation**: A user is created in Supabase Auth (yielding an `auth.users.id`). A corresponding row is inserted into our `public.users` table, storing their `role`, `organization_id`, and linking the `auth_id`.
2. **Login**: The user authenticates via Next.js against Supabase. Supabase returns a JWT and establishes a session.
3. **API Requests**: The Next.js frontend sends the JWT bearer token with every request to the FastAPI backend.
4. **Backend Verification**: 
    - The FastAPI backend validates the JWT using the Supabase Admin client. 
    - It extracts the `user_id` (the `auth_id`) from the verified token payload.
    - It queries the `public.users` table using that `auth_id` to retrieve the internal user object, including their `role`, `organization_id`, and `branch_id`.
5. **Enforcement**: This internal user object is then injected into the request state (e.g., the `CodingState` context for LangGraph). Every downstream database query, pipeline node, and API response dynamically scopes its behavior based on these verified multi-tenant attributes.

This architecture ensures a seamless developer experience (using Supabase tools) while maintaining strict, application-specific B2B security requirements.

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
