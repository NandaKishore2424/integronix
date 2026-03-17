-- Migration: 022_dynamic_pricing_multiplier.sql
-- Description: Adds the cpt_pricing_multiplier to the org_settings table
-- to enable hospital-specific revenue cycle management calculations.

-- Add the new column with a default of 1.0 (standard CMS base rate)
ALTER TABLE public.org_settings 
ADD COLUMN IF NOT EXISTS cpt_pricing_multiplier NUMERIC(5,2) DEFAULT 1.00 NOT NULL;

-- Add a check constraint to ensure the multiplier is valid (e.g., between 0.1 and 10.0)
ALTER TABLE public.org_settings
ADD CONSTRAINT check_cpt_multiplier_range 
CHECK (cpt_pricing_multiplier >= 0.1 AND cpt_pricing_multiplier <= 10.0);

-- Provide a comment for database documentation
COMMENT ON COLUMN public.org_settings.cpt_pricing_multiplier IS 'Multiplier applied to the base CMS CPT price to calculate this specific organizations gross charge.';

-- Update the "Premium Care Institute" to have a 1.8 multiplier
UPDATE public.org_settings
SET cpt_pricing_multiplier = 1.80
FROM public.organizations
WHERE org_settings.organization_id = organizations.id
  AND organizations.name ILIKE '%Premium%';

-- Update "City General Hospital" to a 1.2 multiplier
UPDATE public.org_settings
SET cpt_pricing_multiplier = 1.20
FROM public.organizations
WHERE org_settings.organization_id = organizations.id
  AND organizations.name ILIKE '%City%';
