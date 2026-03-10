-- ============================================================
-- Migration 012: Branches Table
-- A branch is a physical or logical sub-unit of an organization.
-- Example: Apollo Hospitals (org) → MRC Nagar Branch (branch)
--                                 → Greams Road Branch (branch)
-- ============================================================

CREATE TABLE branches (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name            TEXT        NOT NULL,
    code            TEXT,       -- Short internal code e.g. "MRC-01"
    city            TEXT,
    state           TEXT,
    country         TEXT        DEFAULT 'US',
    address         TEXT,
    is_active       BOOLEAN     DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),

    -- A branch name must be unique within an organization
    UNIQUE (organization_id, name)
);

CREATE TRIGGER trg_branches_updated_at
    BEFORE UPDATE ON branches
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Fast lookup: find all branches of an org
CREATE INDEX idx_branches_organization_id ON branches(organization_id);

COMMENT ON TABLE branches IS
'Physical or logical sub-unit of an organization (e.g. hospital wing, clinic location). Cases are tracked per branch for analytics.';
