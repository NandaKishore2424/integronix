-- Migration 016: Add missing CPT and Financial Summary arrays to coding_results
-- This ensures the risk_scoring.py node can persist procedure and pricing data.

ALTER TABLE coding_results
    ADD COLUMN IF NOT EXISTS cpt_codes JSONB,
    ADD COLUMN IF NOT EXISTS financial_summary JSONB;
