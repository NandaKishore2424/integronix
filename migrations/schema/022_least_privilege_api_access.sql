-- ============================================================================
-- 022_least_privilege_api_access.sql
--
-- Deny-by-default access through Supabase's auto-generated Data API (/rest/v1).
--
-- WHY
--   Found while moving the database to the Mumbai project: 14 public tables had
--   row level security disabled, while the anon and authenticated roles held
--   full table privileges (Supabase's "automatically expose new tables"
--   default). The anon key ships in the browser bundle, so anyone could read
--   and write those tables directly, bypassing the backend entirely, including
--   `users` (emails and roles) and `organizations`.
--
-- MODEL AFTER THIS MIGRATION
--   * Every table in `public` has RLS enabled.
--   * `anon` has no table, sequence or function privileges.
--   * `service_role` (the FastAPI backend, server-side only) has DML on every
--     table, sequence usage, and EXECUTE on the RPC functions. It bypasses RLS
--     by design; the backend enforces tenancy itself.
--   * `authenticated` (a signed-in browser) can read only its own user row,
--     its own organisation and that organisation's branches. Organisation
--     admins can also list their organisation's users, and hospital-side
--     admins can add branches. Everything else goes through the backend.
--   * Functions pin their search_path, so a caller cannot redirect name
--     resolution to objects in another schema.
--
-- Idempotent: safe to re-run.
-- ============================================================================

BEGIN;

-- ── 1. RLS on every table ───────────────────────────────────────────────────
DO $$
DECLARE t record;
BEGIN
    FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t.tablename);
    END LOOP;
END $$;

-- ── 2. Table and sequence privileges ────────────────────────────────────────
REVOKE ALL ON ALL TABLES    IN SCHEMA public FROM anon, authenticated;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO service_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role;

-- Objects created later by `postgres` follow the same rule.
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public REVOKE ALL ON TABLES    FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public REVOKE ALL ON SEQUENCES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM PUBLIC, anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO service_role;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO service_role;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO service_role;

-- ── 3. Helpers for browser policies ─────────────────────────────────────────
-- SECURITY DEFINER lets a policy on `users` look up the caller's own row
-- without recursing into that same policy.
CREATE OR REPLACE FUNCTION public.my_org_id()
RETURNS uuid
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT u.organization_id FROM public.users u WHERE u.auth_id = auth.uid()
$$;

CREATE OR REPLACE FUNCTION public.my_role()
RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT u.role FROM public.users u WHERE u.auth_id = auth.uid()
$$;

-- ── 4. Function hardening: pinned search_path, explicit EXECUTE ─────────────
DO $$
DECLARE f record;
BEGIN
    FOR f IN
        SELECT p.oid::regprocedure AS sig, p.prosecdef AS definer, p.proname
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        LEFT JOIN pg_depend d ON d.objid = p.oid AND d.deptype = 'e'
        WHERE n.nspname = 'public' AND d.objid IS NULL          -- skip extension members
    LOOP
        IF f.definer THEN
            EXECUTE format('ALTER FUNCTION %s SET search_path = %L', f.sig, '');
        ELSE
            EXECUTE format('ALTER FUNCTION %s SET search_path = public, extensions', f.sig);
        END IF;
        EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC, anon, authenticated', f.sig);
        EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO service_role', f.sig);
    END LOOP;
END $$;

-- Functions evaluated inside browser-facing policies must be callable by it.
GRANT EXECUTE ON FUNCTION public.my_org_id()           TO authenticated;
GRANT EXECUTE ON FUNCTION public.my_role()             TO authenticated;
GRANT EXECUTE ON FUNCTION public.current_user_org_id() TO authenticated;

-- ── 5. What a signed-in browser may do ──────────────────────────────────────
-- `(SELECT fn())` is evaluated once per statement instead of once per row.

DROP POLICY IF EXISTS users_read_self ON public.users;
CREATE POLICY users_read_self ON public.users
    FOR SELECT TO authenticated
    USING (auth_id = (SELECT auth.uid()));

DROP POLICY IF EXISTS users_admin_read_org ON public.users;
CREATE POLICY users_admin_read_org ON public.users
    FOR SELECT TO authenticated
    USING (
        organization_id = (SELECT public.my_org_id())
        AND (SELECT public.my_role()) = 'admin'
    );

DROP POLICY IF EXISTS organizations_read_own ON public.organizations;
CREATE POLICY organizations_read_own ON public.organizations
    FOR SELECT TO authenticated
    USING (id = (SELECT public.my_org_id()));

DROP POLICY IF EXISTS branches_read_own_org ON public.branches;
CREATE POLICY branches_read_own_org ON public.branches
    FOR SELECT TO authenticated
    USING (organization_id = (SELECT public.my_org_id()));

DROP POLICY IF EXISTS branches_admin_insert ON public.branches;
CREATE POLICY branches_admin_insert ON public.branches
    FOR INSERT TO authenticated
    WITH CHECK (
        organization_id = (SELECT public.my_org_id())
        AND (SELECT public.my_role()) = 'admin'
        AND EXISTS (
            SELECT 1 FROM public.organizations o
            WHERE o.id = organization_id AND o.type <> 'insurance_payer'
        )
    );

GRANT SELECT ON public.users, public.organizations, public.branches TO authenticated;
GRANT INSERT ON public.branches TO authenticated;

COMMIT;
