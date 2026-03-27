-- 019_payer_org_link.sql
-- Links the `payers` table to the `organizations` table so that payer accounts
-- have a dedicated configuration profile.

ALTER TABLE IF EXISTS public.payers
    ADD COLUMN IF NOT EXISTS organization_id UUID REFERENCES public.organizations(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_payers_org_id ON public.payers(organization_id);
