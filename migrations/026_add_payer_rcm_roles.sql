-- ============================================================
-- Migration 026: Add 'payer' and 'rcm' Roles to Users Table
-- Sprint 7 — RBAC Role Synchronization
-- ============================================================
-- The original users table (013) only allowed ('admin', 'auditor', 'coder').
-- Sprint 3 introduced Insurance Payer organizations and Sprint 4 introduced
-- the /payer/* portal, but the DB role constraint was never updated.
-- This migration widens the allowed roles to include:
--   'rcm'   — Revenue Cycle Management staff (claims, billing, analytics)
--   'payer' — Insurance adjudicator (access to /payer/* only)
-- ============================================================

-- Step 1: Drop the old check constraint on users.role by name
ALTER TABLE public.users
    DROP CONSTRAINT IF EXISTS users_role_check;

-- Step 1b: Also expand organizations.type to include 'insurance_payer'
-- (original constraint only allowed hospital/clinic/rcm_vendor/diagnostic_center)
ALTER TABLE public.organizations
    DROP CONSTRAINT IF EXISTS organizations_type_check;

ALTER TABLE public.organizations
    ADD CONSTRAINT organizations_type_check
    CHECK (type IN (
        'hospital',
        'clinic',
        'rcm_vendor',
        'diagnostic_center',
        'insurance_payer'   -- New: for insurance payer orgs like Star Health
    ));

-- Step 2: Re-add the constraint with all 5 valid roles
ALTER TABLE public.users
    ADD CONSTRAINT users_role_check
    CHECK (role IN (
        'admin',    -- Full org access: manage users, view all branches
        'auditor',  -- Read-only across the org (legacy/compliance role)
        'coder',    -- Submit coding cases, view own branch results
        'rcm',      -- Revenue Cycle: manage claims, billing, analytics
        'payer'     -- Insurance adjudicator: /payer/* portal access only
    ));

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
