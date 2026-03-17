-- ============================================================
-- Migration 016: Seed Demo Organization Data
-- Creates a demo hospital hierarchy for POC / hackathon demo.
-- Run AFTER migrations 011–015.
-- ============================================================

-- ── 1. Demo Organization ─────────────────────────────────────
INSERT INTO organizations (id, name, slug, type, country, timezone)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'City General Hospital',
    'city-general-hospital',
    'hospital',
    'US',
    'America/New_York'
) ON CONFLICT (slug) DO NOTHING;


-- ── 2. Branches ──────────────────────────────────────────────
INSERT INTO branches (id, organization_id, name, code, city, state)
VALUES
    (
        '00000000-0000-0000-0000-000000000010',
        '00000000-0000-0000-0000-000000000001',
        'Main Campus — Cardiology',
        'CGH-CARD',
        'New York', 'NY'
    ),
    (
        '00000000-0000-0000-0000-000000000011',
        '00000000-0000-0000-0000-000000000001',
        'North Wing — Endocrinology',
        'CGH-ENDO',
        'New York', 'NY'
    ),
    (
        '00000000-0000-0000-0000-000000000012',
        '00000000-0000-0000-0000-000000000001',
        'South Campus — Orthopaedics',
        'CGH-ORTH',
        'New York', 'NY'
    )
ON CONFLICT DO NOTHING;


-- ── 3. Demo Users ────────────────────────────────────────────
INSERT INTO users (id, organization_id, branch_id, email, full_name, role)
VALUES
    -- Admin: sees everything, no branch restriction
    (
        '00000000-0000-0000-0000-000000000100',
        '00000000-0000-0000-0000-000000000001',
        NULL,
        'admin@citygeneral.demo',
        'Dr. Sarah Chen (Admin)',
        'admin'
    ),
    -- Auditor: reads all results, cannot submit
    (
        '00000000-0000-0000-0000-000000000101',
        '00000000-0000-0000-0000-000000000001',
        NULL,
        'auditor@citygeneral.demo',
        'James Patel (Auditor)',
        'auditor'
    ),
    -- Coder 1: only Cardiology branch
    (
        '00000000-0000-0000-0000-000000000102',
        '00000000-0000-0000-0000-000000000001',
        '00000000-0000-0000-0000-000000000010',
        'coder.cardio@citygeneral.demo',
        'Maria Santos (Coder — Cardiology)',
        'coder'
    ),
    -- Coder 2: only Endocrinology branch
    (
        '00000000-0000-0000-0000-000000000103',
        '00000000-0000-0000-0000-000000000001',
        '00000000-0000-0000-0000-000000000011',
        'coder.endo@citygeneral.demo',
        'Raj Kumar (Coder — Endocrinology)',
        'coder'
    )
ON CONFLICT (email) DO NOTHING;


-- ── 4. Verification query ────────────────────────────────────
-- Run this to confirm everything looks right after seeding:
-- SELECT
--     o.name AS organization,
--     b.name AS branch,
--     u.full_name,
--     u.role,
--     u.email
-- FROM users u
-- JOIN organizations o ON o.id = u.organization_id
-- LEFT JOIN branches b ON b.id = u.branch_id
-- ORDER BY u.role, u.full_name;
-- Migration: 023_seed_premium_org.sql
-- Description: Adds a second demo organization "Premium Care Institute"
-- to demonstrate the dynamic pricing multiplier (set to 1.8x).

-- 1. Insert the Premium Organization
INSERT INTO public.organizations (id, name, slug, type, country, timezone)
VALUES (
    '00000000-0000-0000-0000-000000000002',
    'Premium Care Institute',
    'premium-care-institute',
    'hospital',
    'US',
    'America/New_York'
) ON CONFLICT (id) DO NOTHING;

-- 2. Insert Settings for the Premium Organization (1.8x multiplier)
INSERT INTO public.org_settings (organization_id, icd_version, coding_mode, claim_scheme, cpt_pricing_multiplier)
VALUES (
    '00000000-0000-0000-0000-000000000002',
    'ICD-10',
    'aggressive',
    'private',
    1.80
) ON CONFLICT (organization_id) DO UPDATE 
SET cpt_pricing_multiplier = 1.80;

-- 3. Just in case, ensure City General is also explicitly set to 1.2x
INSERT INTO public.org_settings (organization_id, icd_version, coding_mode, claim_scheme, cpt_pricing_multiplier)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'ICD-10',
    'balanced',
    'private',
    1.20
) ON CONFLICT (organization_id) DO UPDATE 
SET cpt_pricing_multiplier = 1.20;

-- ── 2. Seed Demo Payers ────────────────────────────────────────────────────
INSERT INTO public.payers (name, payer_type, base_allowed_multiplier)
VALUES 
    ('Medicare Complete', 'medicare', 1.00),
    ('BlueShield Corporate', 'commercial', 1.25),
    ('United Healthcare Plus', 'commercial', 1.20),
    ('Aetna Preferred', 'commercial', 1.15)
ON CONFLICT DO NOTHING;


-- Step 3: Seed a demo payer organization and user for testing
-- (Only inserts if the org slug doesn't already exist)

INSERT INTO public.organizations (id, name, slug, type, country, timezone)
VALUES (
    '00000000-0000-0000-0000-000000000002',
    'Star Health Insurance',
    'star-health-insurance',
    'insurance_payer',
    'IN',
    'Asia/Kolkata'
) ON CONFLICT (slug) DO NOTHING;

-- Seed a demo payer user into that org
INSERT INTO public.users (id, organization_id, branch_id, email, full_name, role)
VALUES (
    '00000000-0000-0000-0000-000000000200',
    '00000000-0000-0000-0000-000000000002',
    NULL,
    'adjudicator@starhealth.demo',
    'Priya Nair (Payer Adjudicator)',
    'payer'
) ON CONFLICT (email) DO NOTHING;

-- Seed a demo RCM user in the original hospital org
INSERT INTO public.users (id, organization_id, branch_id, email, full_name, role)
VALUES (
    '00000000-0000-0000-0000-000000000104',
    '00000000-0000-0000-0000-000000000001',
    NULL,
    'rcm@citygeneral.demo',
    'David Kim (RCM Manager)',
    'rcm'
) ON CONFLICT (email) DO NOTHING;

-- Verification Query (run after applying):
-- SELECT id, email, role FROM public.users ORDER BY role, email;
