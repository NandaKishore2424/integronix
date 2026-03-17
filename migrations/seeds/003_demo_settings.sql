-- ── Seed: demo org with ICD-11 defaults ───────────────────────────────────────
INSERT INTO org_settings (organization_id, icd_version, coding_mode, claim_scheme)
SELECT id, 'ICD-11', 'balanced', 'private'
FROM organizations
ON CONFLICT (organization_id) DO NOTHING;
