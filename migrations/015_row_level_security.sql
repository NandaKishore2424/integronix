-- ============================================================
-- Migration 015: Row-Level Security (RLS) Policies
-- Supabase RLS ensures Hospital A can NEVER query Hospital B's data.
-- Even if someone gets a valid JWT, they only see their org's rows.
-- ============================================================

-- ── Enable RLS on the three data tables ─────────────────────
ALTER TABLE clinical_cases  ENABLE ROW LEVEL SECURITY;
ALTER TABLE coding_results  ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log       ENABLE ROW LEVEL SECURITY;

-- ── Helper: Extract org_id from the current user's JWT ───────
-- In Supabase, the JWT carries custom claims.
-- We store organization_id in the JWT under app_metadata.
-- This function reads it safely.
CREATE OR REPLACE FUNCTION current_user_org_id() RETURNS UUID AS $$
BEGIN
    RETURN (
        current_setting('request.jwt.claims', true)::jsonb
        -> 'app_metadata'
        ->> 'organization_id'
    )::UUID;
EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
END;
$$ LANGUAGE plpgsql STABLE SECURITY DEFINER;


-- ── Policies: clinical_cases ─────────────────────────────────
-- Users can only SELECT / INSERT / UPDATE their own org's cases.

CREATE POLICY "org_isolation_clinical_cases_select"
ON clinical_cases FOR SELECT
USING (organization_id = current_user_org_id());

CREATE POLICY "org_isolation_clinical_cases_insert"
ON clinical_cases FOR INSERT
WITH CHECK (organization_id = current_user_org_id());

CREATE POLICY "org_isolation_clinical_cases_update"
ON clinical_cases FOR UPDATE
USING (organization_id = current_user_org_id());


-- ── Policies: coding_results ─────────────────────────────────
CREATE POLICY "org_isolation_coding_results_select"
ON coding_results FOR SELECT
USING (organization_id = current_user_org_id());

CREATE POLICY "org_isolation_coding_results_insert"
ON coding_results FOR INSERT
WITH CHECK (organization_id = current_user_org_id());


-- ── Policies: audit_log ──────────────────────────────────────
CREATE POLICY "org_isolation_audit_log_select"
ON audit_log FOR SELECT
USING (organization_id = current_user_org_id());

CREATE POLICY "org_isolation_audit_log_insert"
ON audit_log FOR INSERT
WITH CHECK (organization_id = current_user_org_id());


-- ── Service role bypass ──────────────────────────────────────
-- The backend uses a service_role key which bypasses RLS.
-- This is intentional: the pipeline writes data on behalf of users.
-- NEVER expose the service_role key to the frontend.

COMMENT ON FUNCTION current_user_org_id() IS
'Reads organization_id from JWT app_metadata. Used in RLS policies to enforce tenant isolation.';
