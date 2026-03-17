# Sprint 7: Authentication & Role-Based Access Control (RBAC)

## Goal
Lock down the application so Coders cannot see Billing/RCM sections, Billers cannot see the Insurance Payer Portal, and unauthorized users cannot access the app at all.

## Current Progress Status
- ✅ **Phase 3 Part 1:** `/auth/login` and `/auth/signup` Next.js pages are already built.
- ✅ **Phase 3 Part 2:** Supabase Auth SDK integration handles JWT issuance. Auth provider exists and binds auth UUIDs to `public.users` table records.
- ✅ **Phase 1 Part 1:** DB table for users exists (`migrations/013_create_users.sql` & `017_add_auth_id_to_users.sql`), and `role` field was updated in `026_add_payer_rcm_roles.sql` to officially add `payer` and `rcm`.
- ✅ **Phase 1 Part 2:** Row-Level Security (RLS) policies exist in `015_row_level_security.sql`, strictly locking down `claims` and `cases` so users *only* see their organization's data based on their JWT role/organization_id.
- ✅ **Phase 2:** `src/middleware.ts` now enforces strict Role-Based routing based on the DB role (e.g., ensuring a hospital coder can't reach `/payer/*` and vice versa).
- ✅ **Phase 3 Part 3:** Frontend layout sidebars dynamically read the JWT/DB role from `AuthProvider` and hide links that the user is not authorized for.

## Completed Work (Sprint 7)

### ✅ 1. Database Role Synchronization (Migration)
- Checked and updated `users` table's `role` check constraint. Added `payer` and `rcm` via `026_add_payer_rcm_roles.sql`.
- Also updated `organizations` type constraint to allow `insurance_payer`.

### ✅ 2. Next.js Middleware Route Enforcement (RBAC)
Updated `src/middleware.ts` to decode the session information safely from Supabase (fetching DB role) to read the user's role.
- If path starts with `/hospital/coder/`, user role must be `coder` or `admin`.
- If path starts with `/hospital/rcm/`, user role must be `rcm` or `admin`.
- If path starts with `/payer/`, user role must be `payer` or `admin`.
- Otherwise, redirects to `/403`.

### ✅ 3. Sidebar UI / Layout Navigation Updates
Updated:
- `frontend/src/app/hospital/layout.tsx`
- `frontend/src/app/payer/layout.tsx`
To read the role from our `AuthProvider` and selectively render the navigation links in the sidebar so users don't see buttons they can't click (using `allowedRoles` array).

### ✅ 4. Create an Error Page
- Generated a generic `403-forbidden` page (`frontend/src/app/403/page.tsx`) to clearly indicate access denial with smart redirect links.

---

*This document serves as the implementation source of truth for completing Sprint 7 and applying strict role-based access controls across the application.*
