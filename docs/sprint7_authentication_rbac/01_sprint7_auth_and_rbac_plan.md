# Sprint 7: Authentication & Role-Based Access Control (RBAC)

## Goal
Lock down the application so Coders cannot see Billing/RCM sections, Billers cannot see the Insurance Payer Portal, and unauthorized users cannot access the app at all.

## Current Progress Status
- ✅ **Phase 3 Part 1:** `/auth/login` and `/auth/signup` Next.js pages are already built.
- ✅ **Phase 3 Part 2:** Supabase Auth SDK integration handles JWT issuance. Auth provider exists and binds auth UUIDs to `public.users` table records.
- 🟡 **Phase 1 Part 1:** DB table for users exists (`migrations/013_create_users.sql` & `017_add_auth_id_to_users.sql`), but the `role` field currently primarily checks for `('admin', 'auditor', 'coder')`. We may need a migration to officially add `payer` and `rcm` (or we need to update the ENUM/constraint).
- 🟡 **Phase 1 Part 2:** Row-Level Security (RLS) policies exist in `015_row_level_security.sql`, but we need to ensure they strictly lock down `claims` and `cases` so users *only* see their organization's data based on their JWT role/organization_id.
- 🟡 **Phase 2:** `src/middleware.ts` currently protects `/hospital/*` and `/payer/*` requiring an active session, but it **does not** do Role-Based routing (e.g., ensuring a hospital coder can't reach `/payer/*` and vice versa). 
- 🔴 **Phase 3 Part 3:** Frontend layout sidebars need updating to dynamically read the JWT/DB role and hide links that the user is not authorized for.

## What Needs to be Done Next (Pending Work)

### 1. Database Role Synchronization (Migration)
- Check and update `users` table's `role` check constraint. Add `payer` and `rcm` if missing.  
  *(Currently, login logic just checks if the user's organization is "Star Health Insurance" and redirects to `/payer/inbox`, which is a bit hardcoded. Let's make it cleanly role-based).*

### 2. Next.js Middleware Route Enforcement (RBAC)
Update `src/middleware.ts` to decode the session information safely from Supabase (or hit an edge route) to read the user's role.
- If path starts with `/hospital/coder/`, user role must be `coder` or `admin`.
- If path starts with `/hospital/rcm/`, user role must be `rcm` or `admin`.
- If path starts with `/payer/`, user role must be `payer`.
- Otherwise, redirect to a `/403` or `/auth/login`.

### 3. Sidebar UI / Layout Navigation Updates
Update:
- `frontend/src/app/hospital/layout.tsx`
- `frontend/src/app/payer/layout.tsx`
To read the role from our `AuthProvider` and selectively render the navigation links in the sidebar so users don't see buttons they can't click.

### 4. Create an Error Page
- Generate a generic `403-forbidden` page (`frontend/src/app/403/page.tsx`) to clearly indicate access denial if someone types the URL manually.

---

*This document serves as the implementation source of truth for completing Sprint 7 and applying strict role-based access controls across the application.*
