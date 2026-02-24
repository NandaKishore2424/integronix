-- ============================================================
-- Migration 006: Audit Log Table
-- Explainability layer — every LangGraph node decision is logged here.
-- Used by @safe_node decorator in agents/node_runner.py
-- ============================================================

CREATE TABLE audit_log (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID,
    node_name           TEXT        NOT NULL,
    -- node names: doc_processing | clinical_extract | snomed_resolve |
    --             snomed_icd_map | icd_embedding | icd_decision |
    --             audit_comparison | risk_scoring

    -- State snapshots for full traceability
    input_snapshot      JSONB,      -- Key state fields going INTO this node
    output_snapshot     JSONB,      -- Key state fields coming OUT of this node

    -- LLM call tracking (only set for clinical_extract node)
    model_name          TEXT,       -- e.g. "llama-3.3-70b-versatile"
    model_version       TEXT,       -- e.g. "2024-12"
    prompt_tokens       INTEGER,
    completion_tokens   INTEGER,
    total_tokens        INTEGER,
    latency_ms          INTEGER,    -- Wall-clock time for this node in ms

    -- Medical standard versions (set for all nodes)
    icd_version         TEXT        DEFAULT 'ICD-10-CM-2024',
    snomed_version      TEXT        DEFAULT 'SNOMED-CT-2024',

    -- Outcome
    status              TEXT        CHECK (status IN ('success', 'fallback_used', 'failed')),
    fallback_reason     TEXT,       -- Populated when status = 'fallback_used'
    error_detail        TEXT,       -- Populated when status = 'failed'

    created_at          TIMESTAMPTZ DEFAULT NOW()
);
