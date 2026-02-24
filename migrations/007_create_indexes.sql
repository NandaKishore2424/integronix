-- ============================================================
-- Migration 007: All Indexes
-- Run AFTER all tables are created and seed data is inserted.
-- Note: ivfflat indexes require at least some rows to build efficiently.
-- ============================================================

-- ── ICD Embedding Index (dense vector search) ─────────────────────────────
-- Used by: icd_embedding node (fallback similarity search)
CREATE INDEX ON icd_codes
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 50);

-- ── SNOMED Embedding Index (dense vector search) ──────────────────────────
-- Used by: snomed_resolve node (embedding fallback)
CREATE INDEX ON snomed_concepts
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 20);

-- ── SNOMED-ICD Mapping Indexes ─────────────────────────────────────────────
-- Used by: snomed_icd_map node (direct mapping lookup)
CREATE INDEX idx_snomed_icd_map_snomed ON snomed_icd_map (snomed_code);
CREATE INDEX idx_snomed_icd_map_icd    ON snomed_icd_map (icd_code);
CREATE INDEX idx_snomed_icd_map_type   ON snomed_icd_map (mapping_type);

-- ── Clinical Cases Index ───────────────────────────────────────────────────
CREATE INDEX idx_clinical_cases_status ON clinical_cases (processing_status);

-- ── Coding Results Indexes ─────────────────────────────────────────────────
CREATE INDEX idx_coding_results_case   ON coding_results (case_id);
CREATE INDEX idx_coding_results_ai     ON coding_results (ai_icd_code);

-- ── Audit Log Indexes ──────────────────────────────────────────────────────
-- Used for: session-level decision trail queries
CREATE INDEX idx_audit_log_session     ON audit_log (session_id);
CREATE INDEX idx_audit_log_node        ON audit_log (node_name);
CREATE INDEX idx_audit_log_created     ON audit_log (created_at DESC);
