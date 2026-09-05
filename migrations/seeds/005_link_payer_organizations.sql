-- ============================================================
-- Seed 005: link payer records to their owning organization
--
-- WHY: routes/claims.py scopes a payer user to the payer records their
-- organization owns (payers.organization_id). A payer row with a NULL
-- organization_id is therefore invisible to everyone — claims routed to it
-- silently disappear from every inbox, because tenant scoping filters them
-- out before the payer ever sees them. There is no error; the claim simply
-- cannot be adjudicated by anyone.
--
-- "Global Health Insurance" was in exactly that state. Matching on name is
-- acceptable here because organizations.slug/name is unique per tenant and
-- this is demo seed data.
-- ============================================================

UPDATE public.payers p
   SET organization_id = o.id,
       updated_at      = now()
  FROM public.organizations o
 WHERE p.organization_id IS NULL
   AND o.type = 'insurance_payer'
   AND lower(o.name) = lower(p.name);

-- Verification — every payer record should now have an owner:
--   SELECT p.name, o.name AS owning_org
--     FROM public.payers p
--     LEFT JOIN public.organizations o ON o.id = p.organization_id
--    ORDER BY p.name;
