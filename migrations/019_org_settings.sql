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

-- ── Seed: demo org with ICD-11 defaults ───────────────────────────────────────
-- NOTE: Replace the UUID below with your actual demo org ID from the organizations table
-- SELECT id FROM organizations LIMIT 5;  -- run this first to find org IDs

INSERT INTO org_settings (organization_id, icd_version, coding_mode, claim_scheme)
SELECT id, 'ICD-11', 'balanced', 'private'
FROM   organizations
ON CONFLICT (organization_id) DO NOTHING;

-- Verify
SELECT o.name, s.icd_version, s.coding_mode, s.claim_scheme
FROM   org_settings s
JOIN   organizations o ON o.id = s.organization_id;
