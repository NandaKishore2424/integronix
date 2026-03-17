-- ============================================================
-- Migration: 003_e2e_demo_seed.sql
-- Description: E2E Testing Seed Data for Integronix
-- Creates a pristine testing environment mapping the full RCM flow.
-- ============================================================

-- ── 1. The Healthcare Provider (Hospital) ─────────────────────────
INSERT INTO organizations (id, name, slug, type, country, timezone)
VALUES (
    'f2a96996-8576-4328-91fb-680c2fdb21d5',
    'Saveetha Hospitals',
    'saveetha-hospitals',
    'hospital',
    'IN',
    'Asia/Kolkata'
) ON CONFLICT (slug) DO NOTHING;

-- Settings for Saveetha
INSERT INTO org_settings (organization_id, icd_version, coding_mode, claim_scheme, cpt_pricing_multiplier)
VALUES (
    'f2a96996-8576-4328-91fb-680c2fdb21d5',
    'ICD-11',
    'balanced',
    'private',
    1.00
) ON CONFLICT (organization_id) DO NOTHING;

-- Branches for Saveetha
INSERT INTO branches (id, organization_id, name, code, city, state)
VALUES
    (
        'e98f4cd5-420a-4da2-841f-ed56c4125b34',
        'f2a96996-8576-4328-91fb-680c2fdb21d5',
        'Saveetha Main Branch (Chetipedu)',
        'SH-MAIN',
        'Chennai', 'TN'
    ),
    (
        'c75dcb09-43c2-463e-b87d-81283c21b219',
        'f2a96996-8576-4328-91fb-680c2fdb21d5',
        'Saveetha Dental Hospital (Poonamalee)',
        'SH-DENT',
        'Chennai', 'TN'
    )
ON CONFLICT DO NOTHING;

-- ── 2. The Insurance Payer ───────────────────────────────────────
-- Global Health Insurance (Tenant)
INSERT INTO organizations (id, name, slug, type, country, timezone)
VALUES (
    '8b19d426-ed87-4aa7-a877-a88ae1b0e1b6',
    'Global Health Insurance',
    'global-health-insurance',
    'insurance_payer',
    'IN',
    'Asia/Kolkata'
) ON CONFLICT (slug) DO NOTHING;

-- Global Health (Payer Entity linked to Claims)
INSERT INTO payers (id, name, payer_type, base_allowed_multiplier)
VALUES (
    '1f46b28a-8c9a-412f-937b-9fadc48011c7',
    'Global Health Insurance',
    'commercial',
    1.15
) ON CONFLICT DO NOTHING;

-- ── 3. The Users ─────────────────────────────────────────────────
INSERT INTO users (id, organization_id, branch_id, email, full_name, role)
VALUES
    -- Nanda Kishore (Medical Coder at Main Branch)
    (
        'd01f92e4-6a84-486a-8b39-1fb428af4c91',
        'f2a96996-8576-4328-91fb-680c2fdb21d5',
        'e98f4cd5-420a-4da2-841f-ed56c4125b34',
        'nanda@saveetha.demo',
        'Nanda Kishore',
        'coder'
    ),
    -- Subashini (RCM Manager for all of Saveetha)
    (
        'a49bf301-729c-4862-8495-2c8c0f592182',
        'f2a96996-8576-4328-91fb-680c2fdb21d5',
        NULL,
        'subashini@saveetha.demo',
        'Subashini',
        'rcm'
    ),
    -- Nathin (Payer Adjudicator at Global Health)
    (
        'b86c2f9d-7a0e-4363-9e12-4f81c6204c32',
        '8b19d426-ed87-4aa7-a877-a88ae1b0e1b6',
        NULL,
        'nathin@globalhealth.demo',
        'Nathin',
        'payer'
    )
ON CONFLICT (email) DO NOTHING;
