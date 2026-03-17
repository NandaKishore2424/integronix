-- ============================================================
-- Migration 006: Audit Log Table
-- Explainability layer — every LangGraph node decision is logged here.
-- Used by @safe_node decorator in agents/node_runner.py
-- ============================================================

CREATE TABLE audit_log (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID,
    node_name           TEXT        NOT NULL,
    -- node names: doc_processing | clinical_extract | snomed_resolve |
    --             snomed_icd_map | icd_embedding | icd_decision |
    --             audit_comparison | risk_scoring

    -- State snapshots for full traceability
    input_snapshot      JSONB,      -- Key state fields going INTO this node
    output_snapshot     JSONB,      -- Key state fields coming OUT of this node

    -- LLM call tracking (only set for clinical_extract node)
    model_name          TEXT,       -- e.g. "llama-3.3-70b-versatile"
    model_version       TEXT,       -- e.g. "2024-12"
    prompt_tokens       INTEGER,
    completion_tokens   INTEGER,
    total_tokens        INTEGER,
    latency_ms          INTEGER,    -- Wall-clock time for this node in ms

    -- Medical standard versions (set for all nodes)
    icd_version         TEXT        DEFAULT 'ICD-10-CM-2024',
    snomed_version      TEXT        DEFAULT 'SNOMED-CT-2024',

    -- Outcome
    status              TEXT        CHECK (status IN ('success', 'fallback_used', 'failed')),
    fallback_reason     TEXT,       -- Populated when status = 'fallback_used'
    error_detail        TEXT,       -- Populated when status = 'failed'

    created_at          TIMESTAMPTZ DEFAULT NOW()
);
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
-- Migration: 019_org_settings.sql
-- Purpose: Per-organisation configuration table
-- Controls ICD version, coding mode, and insurance scheme per hospital
-- Run this in: Supabase → SQL Editor → New Query → Run

-- ── Create org_settings table ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS org_settings (
    organization_id UUID        PRIMARY KEY
                                REFERENCES organizations(id) ON DELETE CASCADE,
    icd_version     TEXT        NOT NULL DEFAULT 'ICD-11'
                                CHECK (icd_version IN ('ICD-10', 'ICD-11')),
    coding_mode     TEXT        NOT NULL DEFAULT 'balanced'
                                CHECK (coding_mode IN ('aggressive', 'balanced', 'conservative')),
    claim_scheme    TEXT        NOT NULL DEFAULT 'private'
                                CHECK (claim_scheme IN (
                                    'ayushman_bharat',  -- PM-JAY govt scheme
                                    'cghs',             -- Central Govt Health Scheme
                                    'esi',              -- Employee State Insurance
                                    'private'           -- Private insurer / TPA
                                )),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Comments ──────────────────────────────────────────────────────────────────
COMMENT ON TABLE org_settings IS
    'Per-organisation runtime configuration. Controls ICD version (ICD-10/11),
     coding aggressiveness (affects revenue vs audit risk), and insurance scheme.
     Seeded with defaults — update per hospital onboarding.';

COMMENT ON COLUMN org_settings.icd_version IS
    'ICD-11 = ABDM/Ayushman Bharat aligned (recommended).
     ICD-10 = Legacy private insurer systems still in transition.
     Pipeline reads this to select the correct WHO ICD API endpoint.';

COMMENT ON COLUMN org_settings.coding_mode IS
    'aggressive   = maximise specificity and revenue capture (higher audit risk).
     balanced     = standard clinical coding best practices (default).
     conservative = minimal coding, lowest audit risk (govt schemes).';

COMMENT ON COLUMN org_settings.claim_scheme IS
    'Insurance scheme context. Affects coding strictness and output format.
     ayushman_bharat/cghs = ICD-11 mandatory, conservative mode recommended.
     private              = ICD-10 or ICD-11 depending on payer.';

-- ── Auto-update timestamp trigger ─────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_org_settings_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER org_settings_updated_at
    BEFORE UPDATE ON org_settings
    FOR EACH ROW
    EXECUTE FUNCTION update_org_settings_updated_at();

-- ── RLS: org members can read their own settings ──────────────────────────────
ALTER TABLE org_settings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "org_settings_read_own"
    ON org_settings FOR SELECT
    USING (
        organization_id IN (
            SELECT organization_id FROM users
            WHERE id = auth.uid()
        )
    );

-- Only service role can write (admins use service role key)
CREATE POLICY "org_settings_admin_write"
    ON org_settings FOR ALL
    USING (auth.role() = 'service_role');


