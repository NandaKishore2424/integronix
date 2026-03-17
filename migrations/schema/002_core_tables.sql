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
                    CHECK (type IN ('hospital', 'clinic', 'rcm_vendor', 'diagnostic_center', 'insurance_payer')),
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
                        'admin',    -- Full org access: manage users, view all branches
                        'auditor',  -- Read-only across the org (legacy/compliance role)
                        'coder',    -- Submit coding cases, view own branch results
                        'rcm',      -- Revenue Cycle: manage claims, billing, analytics
                        'payer'     -- Insurance adjudicator: /payer/* portal access only
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
-- ============================================================
-- Migration 017: Link Supabase Auth to public.users
-- Adds auth_id column so each public.users row links to
-- the corresponding auth.users (Supabase Auth) record.
-- Run in Supabase SQL editor BEFORE testing auth.
-- ============================================================

ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS auth_id UUID UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE;

-- Index for fast auth_id lookups (used on every page load)
CREATE INDEX IF NOT EXISTS idx_users_auth_id ON public.users(auth_id);

COMMENT ON COLUMN public.users.auth_id IS
'Links to Supabase Auth user (auth.users.id). Set when user is created via supabase.auth.signUp().';
-- ============================================================
-- Migration 014: Add Multi-Tenant Columns to Existing Tables
-- Adds organization_id + branch_id + submitted_by to:
--   clinical_cases, coding_results, audit_log
-- Uses ALTER TABLE so existing data is preserved.
-- New columns are nullable initially → you can backfill if needed.
-- ============================================================

-- ── 14a: clinical_cases ──────────────────────────────────────
ALTER TABLE clinical_cases
    ADD COLUMN IF NOT EXISTS organization_id UUID REFERENCES organizations(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS branch_id       UUID REFERENCES branches(id)       ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS submitted_by    UUID REFERENCES users(id)          ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS document_source TEXT DEFAULT 'raw_text'
                             CHECK (document_source IN ('raw_text', 'pdf_upload', 'ehr_import')),
    ADD COLUMN IF NOT EXISTS original_filename TEXT,  -- Original file name if PDF uploaded
    ADD COLUMN IF NOT EXISTS ocr_used        BOOLEAN DEFAULT FALSE; -- TRUE if Tesseract OCR was used

-- Index for fast org-level queries
CREATE INDEX IF NOT EXISTS idx_clinical_cases_org_id    ON clinical_cases(organization_id);
CREATE INDEX IF NOT EXISTS idx_clinical_cases_branch_id ON clinical_cases(branch_id);


-- ── 14b: coding_results ─────────────────────────────────────
ALTER TABLE coding_results
    ADD COLUMN IF NOT EXISTS organization_id UUID REFERENCES organizations(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS branch_id       UUID REFERENCES branches(id)       ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_coding_results_org_id    ON coding_results(organization_id);
CREATE INDEX IF NOT EXISTS idx_coding_results_branch_id ON coding_results(branch_id);


-- ── 14c: audit_log ──────────────────────────────────────────
ALTER TABLE audit_log
    ADD COLUMN IF NOT EXISTS organization_id UUID REFERENCES organizations(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS branch_id       UUID REFERENCES branches(id)       ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_audit_log_org_id    ON audit_log(organization_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_branch_id ON audit_log(branch_id);


COMMENT ON COLUMN clinical_cases.organization_id IS 'Which hospital/org submitted this case';
COMMENT ON COLUMN clinical_cases.branch_id       IS 'Which branch (e.g. cardiology wing) submitted this case';
COMMENT ON COLUMN clinical_cases.submitted_by    IS 'Which user (coder) submitted this case';
COMMENT ON COLUMN clinical_cases.ocr_used        IS 'TRUE when Tesseract OCR was used to extract text from a scanned PDF';
