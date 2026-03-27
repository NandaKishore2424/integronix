-- 018_payer_custom_rules.sql
-- Adds a JSONB column to the payers table to store flexible custom auto-approve rules.
-- Each element inside the array is a rule object evaluated at claim submission time.
--
-- Supported rule_type values (enforced by payer_policy_gate.py):
--   "max_amount"           → block auto-approve if total_billed_amount > threshold (INR)
--   "exclude_cpt_prefix"   → block auto-approve if any CPT code starts with code_prefix
--   "require_min_age"      → block auto-approve if patient age < min_age (years)
--   "require_max_age"      → block auto-approve if patient age > max_age (years)
--
-- Example value:
-- '[
--    {"rule_type": "max_amount",         "threshold": 500000, "label": "No auto-approve above ₹5 lakh"},
--    {"rule_type": "exclude_cpt_prefix",  "code_prefix": "274",  "label": "All arthroplasty → manual review"},
--    {"rule_type": "require_max_age",     "max_age": 70,          "label": "Elderly patients need review"}
-- ]'

ALTER TABLE IF EXISTS public.payers
    ADD COLUMN IF NOT EXISTS auto_approve_custom_rules JSONB NOT NULL DEFAULT '[]'::jsonb;

COMMENT ON COLUMN public.payers.auto_approve_custom_rules IS
    'Array of payer-defined custom logic rules evaluated before auto-approval. '
    'Each object must contain at minimum: rule_type (string), label (string), and '
    'the type-specific threshold field (threshold, code_prefix, min_age, max_age).';
