-- Migration 017: Payer Code Edits — TICKET-04
-- Creates the payer_code_edits audit table and adds payer_edited flag to claims.

-- 1. Extend claims table with payer-edit metadata
ALTER TABLE claims
    ADD COLUMN IF NOT EXISTS payer_edited      BOOLEAN  DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS payer_edit_reason TEXT;

-- 2. Create the granular code-edit audit table
CREATE TABLE IF NOT EXISTS payer_code_edits (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id        UUID         NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
    edited_by       UUID,                        -- payer user id (nullable for now, populated when RBAC is full)
    original_codes  JSONB        NOT NULL,        -- snapshot: { icd_codes: [...], cpt_codes: [...] }
    edited_codes    JSONB        NOT NULL,        -- payer-supplied corrected codes
    edit_reason     TEXT         NOT NULL,        -- required: payer must justify the change
    edited_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Index for quick lookup of all edits for a given claim
CREATE INDEX IF NOT EXISTS idx_payer_code_edits_claim_id ON payer_code_edits(claim_id);
