-- Migration: 024_payer_system.sql
-- Description: Creates the Payer and Claims tables to support the RCM post-coding workflow.
-- Run this in: Supabase → SQL Editor → New Query → Run

-- ── 1. Payers Table ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.payers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    payer_type TEXT NOT NULL 
        CHECK (payer_type IN ('medicare', 'medicaid', 'commercial', 'uninsured')),
    base_allowed_multiplier NUMERIC(5,2) DEFAULT 1.00 NOT NULL, -- Payer pays this multiple of CMS base rates
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE public.payers IS 'Insurance companies or entities responsible for reimbursing hospitals. The base_allowed_multiplier dictates their standard active contract rate compared to baseline Medicare (1.0).';

-- ── 2. Seed Demo Payers ────────────────────────────────────────────────────
INSERT INTO public.payers (name, payer_type, base_allowed_multiplier)
VALUES 
    ('Medicare Complete', 'medicare', 1.00),
    ('BlueShield Corporate', 'commercial', 1.25),
    ('United Healthcare Plus', 'commercial', 1.20),
    ('Aetna Preferred', 'commercial', 1.15)
ON CONFLICT DO NOTHING;

-- ── 3. Claims Table ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.claims (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL, -- Links back to the coding analysis session
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    payer_id UUID REFERENCES public.payers(id),
    
    patient_name TEXT,
    patient_dob DATE,
    
    -- Claim Lifecycle Status
    status TEXT DEFAULT 'DRAFT' NOT NULL
        CHECK (status IN ('DRAFT', 'SUBMITTED', 'ADJUDICATING', 'PAID', 'DENIED', 'PARTIALLY_PAID')),
    
    -- Financials (RCM Metrics)
    total_billed_amount NUMERIC(10,2) DEFAULT 0.00,       -- Hospital Gross Charge (what hospital asked for)
    total_allowed_amount NUMERIC(10,2) DEFAULT 0.00,      -- Payer Approved Amount (contractual allowed)
    total_paid_amount NUMERIC(10,2) DEFAULT 0.00,         -- What payer actually pays
    patient_responsibility NUMERIC(10,2) DEFAULT 0.00,    -- Co-pay / Deductible amount
    
    -- Data Payload
    claim_data JSONB,         -- Snapshots the ICD, CPT, and financial_summary from the coding session
    submission_notes TEXT,    -- Optional notes from the medical coder
    denial_reason TEXT,       -- Reason text if the claim is denied by the payer
    
    -- Timestamps
    submitted_at TIMESTAMPTZ,
    adjudicated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE public.claims IS 'The core RCM entity. Represents a billed claim submitted to a payer, capturing the financial lifecycle from DRAFT to PAID/DENIED.';

-- Index for fast lookup by session and org
CREATE INDEX IF NOT EXISTS idx_claims_session_id ON public.claims(session_id);
CREATE INDEX IF NOT EXISTS idx_claims_org_id ON public.claims(organization_id);

-- ── 4. Triggers & RLS ──────────────────────────────────────────────────────

-- Auto-update trigger reusing the existing function from organizations
CREATE TRIGGER trg_claims_updated_at
    BEFORE UPDATE ON public.claims
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Enable Row Level Security
ALTER TABLE public.claims ENABLE ROW LEVEL SECURITY;

-- Admins and Service Roles can do anything
CREATE POLICY "claims_service_role"
    ON public.claims FOR ALL
    USING (auth.role() = 'service_role');

-- Organizational users can read and write claims belonging to their org
CREATE POLICY "claims_org_access"
    ON public.claims FOR ALL
    USING (
        organization_id IN (
            SELECT organization_id FROM public.users
            WHERE id = auth.uid()
        )
    )
    WITH CHECK (
        organization_id IN (
            SELECT organization_id FROM public.users
            WHERE id = auth.uid()
        )
    );
