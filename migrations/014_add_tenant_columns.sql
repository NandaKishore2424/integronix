-- ============================================================
-- Migration 014: Add Multi-Tenant Columns to Existing Tables
-- Adds organization_id + branch_id + submitted_by to:
--   clinical_cases, coding_results, audit_log
-- Uses ALTER TABLE so existing data is preserved.
-- New columns are nullable initially → you can backfill if needed.
-- ============================================================

-- ── 14a: clinical_cases ──────────────────────────────────────
ALTER TABLE clinical_cases
    ADD COLUMN IF NOT EXISTS organization_id UUID REFERENCES organizations(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS branch_id       UUID REFERENCES branches(id)       ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS submitted_by    UUID REFERENCES users(id)          ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS document_source TEXT DEFAULT 'raw_text'
                             CHECK (document_source IN ('raw_text', 'pdf_upload', 'ehr_import')),
    ADD COLUMN IF NOT EXISTS original_filename TEXT,  -- Original file name if PDF uploaded
    ADD COLUMN IF NOT EXISTS ocr_used        BOOLEAN DEFAULT FALSE; -- TRUE if Tesseract OCR was used

-- Index for fast org-level queries
CREATE INDEX IF NOT EXISTS idx_clinical_cases_org_id    ON clinical_cases(organization_id);
CREATE INDEX IF NOT EXISTS idx_clinical_cases_branch_id ON clinical_cases(branch_id);


-- ── 14b: coding_results ─────────────────────────────────────
ALTER TABLE coding_results
    ADD COLUMN IF NOT EXISTS organization_id UUID REFERENCES organizations(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS branch_id       UUID REFERENCES branches(id)       ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_coding_results_org_id    ON coding_results(organization_id);
CREATE INDEX IF NOT EXISTS idx_coding_results_branch_id ON coding_results(branch_id);


-- ── 14c: audit_log ──────────────────────────────────────────
ALTER TABLE audit_log
    ADD COLUMN IF NOT EXISTS organization_id UUID REFERENCES organizations(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS branch_id       UUID REFERENCES branches(id)       ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_audit_log_org_id    ON audit_log(organization_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_branch_id ON audit_log(branch_id);


COMMENT ON COLUMN clinical_cases.organization_id IS 'Which hospital/org submitted this case';
COMMENT ON COLUMN clinical_cases.branch_id       IS 'Which branch (e.g. cardiology wing) submitted this case';
COMMENT ON COLUMN clinical_cases.submitted_by    IS 'Which user (coder) submitted this case';
COMMENT ON COLUMN clinical_cases.ocr_used        IS 'TRUE when Tesseract OCR was used to extract text from a scanned PDF';
