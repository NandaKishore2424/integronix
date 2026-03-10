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
