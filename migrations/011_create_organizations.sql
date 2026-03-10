-- ============================================================
-- Migration 011: Organizations Table
-- Top-level tenant. Could be a hospital, clinic, or RCM vendor.
-- Every piece of data in the system belongs to an organization.
-- ============================================================

CREATE TABLE organizations (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT        NOT NULL,
    slug            TEXT        UNIQUE NOT NULL,  -- URL-safe identifier e.g. "city-general-hospital"
    type            TEXT        NOT NULL
                    CHECK (type IN ('hospital', 'clinic', 'rcm_vendor', 'diagnostic_center')),
    country         TEXT        DEFAULT 'US',
    timezone        TEXT        DEFAULT 'America/New_York',
    is_active       BOOLEAN     DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Trigger: auto-update updated_at on any row change
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_organizations_updated_at
    BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

COMMENT ON TABLE organizations IS
'Top-level tenant entity. A hospital group, clinic chain, or RCM vendor. All clinical data is scoped to one organization.';
