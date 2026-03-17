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
