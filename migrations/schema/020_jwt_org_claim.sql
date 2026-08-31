-- ============================================================================
-- 020_jwt_org_claim.sql
--
-- Makes the RLS policies from 006_audit_and_security.sql actually enforceable.
--
-- Those policies call current_user_org_id(), which reads
--   request.jwt.claims -> 'app_metadata' ->> 'organization_id'
-- but nothing has ever written that claim. It has been NULL for every user
-- since the policies were created, so `organization_id = current_user_org_id()`
-- has always evaluated false. The policies were dormant rather than enforcing —
-- invisible until now only because the backend connects with the service role,
-- which bypasses RLS entirely.
--
-- This migration backfills the claim for existing users and keeps it in sync
-- going forward.
--
-- ⚠ ORDER OF OPERATIONS — read before enabling DB_FORWARD_USER_JWT:
--    1. Run this migration.
--    2. Every user must obtain a NEW access token. JWT claims are baked in at
--       issue time; existing sessions keep the old claim-less token until it
--       refreshes (Supabase default: 1 hour) or the user signs in again.
--    3. Only then set DB_FORWARD_USER_JWT=true.
--    Flipping the flag before step 2 completes will deny every tenant-scoped
--    query for users still holding an old token.
--
-- Application-layer tenant checks (auth.Principal.assert_org) do not depend on
-- any of this and are always in force.
-- ============================================================================

-- ── 1. Backfill: copy organization_id into each auth user's app_metadata ─────
-- COALESCE preserves any other app_metadata keys already present
-- (e.g. `provider`, `providers`, which Supabase manages itself).

UPDATE auth.users AS au
SET raw_app_meta_data =
        COALESCE(au.raw_app_meta_data, '{}'::jsonb)
        || jsonb_build_object('organization_id', u.organization_id::text)
FROM public.users AS u
WHERE u.auth_id = au.id
  AND u.organization_id IS NOT NULL
  AND COALESCE(
          au.raw_app_meta_data -> 'app_metadata' ->> 'organization_id',
          au.raw_app_meta_data ->> 'organization_id'
      ) IS DISTINCT FROM u.organization_id::text;


-- ── 2. Keep it in sync ───────────────────────────────────────────────────────
-- Fires whenever a public.users row is linked to an auth user or moved between
-- organizations. Without this, a user created after the backfill would have no
-- claim and would be denied by RLS.

CREATE OR REPLACE FUNCTION public.sync_org_claim_to_auth_user()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.auth_id IS NULL OR NEW.organization_id IS NULL THEN
        RETURN NEW;
    END IF;

    UPDATE auth.users
    SET raw_app_meta_data =
            COALESCE(raw_app_meta_data, '{}'::jsonb)
            || jsonb_build_object('organization_id', NEW.organization_id::text)
    WHERE id = NEW.auth_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, auth;

COMMENT ON FUNCTION public.sync_org_claim_to_auth_user() IS
'Mirrors public.users.organization_id into auth.users.raw_app_meta_data so that
current_user_org_id() can read it from the JWT. SECURITY DEFINER because
auth.users is not writable by the application role.';

DROP TRIGGER IF EXISTS trg_sync_org_claim ON public.users;

CREATE TRIGGER trg_sync_org_claim
    AFTER INSERT OR UPDATE OF auth_id, organization_id ON public.users
    FOR EACH ROW
    EXECUTE FUNCTION public.sync_org_claim_to_auth_user();


-- ── 3. Harden the claim reader ───────────────────────────────────────────────
-- The original only looked under an 'app_metadata' key. Depending on how the
-- token is minted, the claim can appear either nested under app_metadata or at
-- the top level of request.jwt.claims. Accept both so enabling forwarding does
-- not hinge on that detail.

CREATE OR REPLACE FUNCTION current_user_org_id() RETURNS UUID AS $$
DECLARE
    claims jsonb;
    org    text;
BEGIN
    claims := current_setting('request.jwt.claims', true)::jsonb;

    org := COALESCE(
        claims -> 'app_metadata' ->> 'organization_id',
        claims ->> 'organization_id'
    );

    IF org IS NULL OR org = '' THEN
        RETURN NULL;
    END IF;

    RETURN org::uuid;
EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
END;
$$ LANGUAGE plpgsql STABLE SECURITY DEFINER;

COMMENT ON FUNCTION current_user_org_id() IS
'Reads organization_id from the request JWT (app_metadata or top level).
Returns NULL when absent, which makes every org-isolation policy deny —
fail-closed by design. Populated by migration 020.';


-- ── 4. Prevent the double-billing race in claims ─────────────────────────────
-- routes/claims.py guards /submit with a read-then-insert on session_id, which
-- two concurrent requests can both pass. Enforce it where it cannot race.
-- Partial index so historical rows with a NULL session_id are unaffected.

CREATE UNIQUE INDEX IF NOT EXISTS uq_claims_session_id
    ON public.claims (session_id)
    WHERE session_id IS NOT NULL;

COMMENT ON INDEX public.uq_claims_session_id IS
'One claim per coding session. Backstops the application-level duplicate check
in POST /api/v1/claims/submit, which is racy on its own.';


-- ── 5. Verification ──────────────────────────────────────────────────────────
-- Expect zero rows. Any row listed here is a user who would be denied by RLS
-- once DB_FORWARD_USER_JWT is enabled.
--
--   SELECT u.email, u.organization_id
--   FROM public.users u
--   JOIN auth.users au ON au.id = u.auth_id
--   WHERE au.raw_app_meta_data ->> 'organization_id' IS DISTINCT FROM
--         u.organization_id::text;
