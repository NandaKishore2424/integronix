-- Migration: 025_audit_trails.sql
-- Description: Creates the claim_audit_logs table to provide an immutable history of claim status changes.
-- Run this in: Supabase → SQL Editor → New Query → Run

-- ── 1. Update Claims Status ENUM (adding APPEALED) ─────────────────────────
-- PostgreSQL doesn't easily let you alter a check constraint without dropping it.
-- We'll drop the old constraint and add a new one that includes 'APPEALED' for Sprint 6.
ALTER TABLE public.claims DROP CONSTRAINT IF EXISTS claims_status_check;
ALTER TABLE public.claims ADD CONSTRAINT claims_status_check 
    CHECK (status IN ('DRAFT', 'SUBMITTED', 'ADJUDICATING', 'PAID', 'DENIED', 'PARTIALLY_PAID', 'APPEALED'));


-- ── 2. Claim Audit Logs Table ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.claim_audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id UUID NOT NULL REFERENCES public.claims(id) ON DELETE CASCADE,
    previous_status TEXT,
    new_status TEXT NOT NULL,
    changed_by_user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL, -- Who made the change
    action_notes TEXT, -- e.g., "Auto-denied by Rules Engine: Gender mismatch", "Approved by manual adjuster"
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE public.claim_audit_logs IS 'Immutable ledger tracking every state change of a claim for HIPAA compliance and SOC2 auditing.';

-- Index for fast lookups by claim
CREATE INDEX IF NOT EXISTS idx_claim_audit_logs_claim_id ON public.claim_audit_logs(claim_id);

-- ── 3. RLS for Audit Logs ──────────────────────────────────────────────────
ALTER TABLE public.claim_audit_logs ENABLE ROW LEVEL SECURITY;

-- Admins and Service Roles can do anything
CREATE POLICY "audit_logs_service_role"
    ON public.claim_audit_logs FOR ALL
    USING (auth.role() = 'service_role');

-- Organizational users can read audit logs for claims belonging to their org
CREATE POLICY "audit_logs_org_read"
    ON public.claim_audit_logs FOR SELECT
    USING (
        claim_id IN (
            SELECT id FROM public.claims
            WHERE organization_id IN (
                SELECT organization_id FROM public.users
                WHERE id = auth.uid()
            )
        )
    );
