-- ============================================================
-- Migration 013: Users Table
-- A user belongs to an organization AND optionally a branch.
-- Roles: admin (org-wide), auditor (read-only), coder (submit cases)
-- ============================================================

CREATE TABLE users (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    branch_id       UUID        REFERENCES branches(id) ON DELETE SET NULL,
    -- branch_id is nullable: admin users are org-wide, not branch-specific

    email           TEXT        NOT NULL UNIQUE,
    full_name       TEXT        NOT NULL,
    role            TEXT        NOT NULL DEFAULT 'coder'
                    CHECK (role IN (
                        'admin',    -- Full org access, manage users, view all branches
                        'auditor',  -- Read-only across the org
                        'coder'     -- Can submit cases, view own branch results only
                    )),

    is_active       BOOLEAN     DEFAULT TRUE,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Indexes for common lookups
CREATE INDEX idx_users_organization_id ON users(organization_id);
CREATE INDEX idx_users_branch_id       ON users(branch_id);
CREATE INDEX idx_users_email           ON users(email);

COMMENT ON TABLE users IS
'Platform users. Each user belongs to one organization and optionally one branch. Roles determine what data they can access.';
