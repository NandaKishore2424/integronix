-- ============================================================
-- Migration 005: Revenue Lookup Table
-- DRG-based reimbursement reference per ICD code
-- ============================================================

CREATE TABLE revenue_lookup (
    id                  SERIAL      PRIMARY KEY,
    icd_code            TEXT        REFERENCES icd_codes(code),
    drg_group           TEXT,               -- e.g. "DRG-637", "DRG-291"
    base_reimbursement  NUMERIC,            -- Base Medicare reimbursement ($)
    cc_adjustment       NUMERIC DEFAULT 0,  -- Added when CC present
    mcc_adjustment      NUMERIC DEFAULT 0,  -- Added when MCC present
    effective_year      TEXT    DEFAULT '2024',
    notes               TEXT
);
