-- 015_payer_auto_approve_policies.sql
-- Adds payer-configurable automation/policy gate settings.

ALTER TABLE IF EXISTS public.payers
    ADD COLUMN IF NOT EXISTS auto_approve_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS auto_approve_confidence_min NUMERIC(5,2) NOT NULL DEFAULT 0.80,
    ADD COLUMN IF NOT EXISTS auto_approve_max_risk NUMERIC(5,2) NOT NULL DEFAULT 0.35,
    ADD COLUMN IF NOT EXISTS auto_approve_requires_patient_dob BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS auto_approve_requires_patient_sex BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS auto_approve_payer_responsibility_pct NUMERIC(5,2) NOT NULL DEFAULT 0.80,
    ADD COLUMN IF NOT EXISTS accepted_icd_versions JSONB NOT NULL DEFAULT '["ICD-10","ICD-11"]'::jsonb;

