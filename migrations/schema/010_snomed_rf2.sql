-- ============================================================
-- Migration 010: SNOMED CT RF2 Core Tables (Descriptions, Relationships, Refsets)
-- Extends existing snomed_concepts + snomed_icd_map
-- ============================================================

-- 10a: SNOMED Descriptions (RF2 Snapshot)
CREATE TABLE IF NOT EXISTS snomed_descriptions (
    id              BIGINT      PRIMARY KEY,               -- RF2 description id
    concept_id      TEXT        NOT NULL REFERENCES snomed_concepts(snomed_code) ON DELETE CASCADE,
    term            TEXT        NOT NULL,                  -- FSN or synonym
    type_id         TEXT        NOT NULL,                  -- RF2 typeId (FSN, synonym)
    language_code   TEXT        NOT NULL,                  -- e.g. 'en'
    is_active       BOOLEAN     DEFAULT TRUE,
    effective_time  DATE        NOT NULL
);

-- 10b: SNOMED Relationships (RF2 Snapshot)
CREATE TABLE IF NOT EXISTS snomed_relationships (
    id                  BIGINT  PRIMARY KEY,               -- RF2 relationship id
    source_id           TEXT    NOT NULL,                  -- source concept id
    destination_id      TEXT    NOT NULL,                  -- destination concept id
    type_id             TEXT    NOT NULL,                  -- relationship type
    relationship_group  INT     DEFAULT 0,
    is_active           BOOLEAN DEFAULT TRUE,
    effective_time      DATE    NOT NULL
);

-- 10c: SNOMED Refsets (Generic)
CREATE TABLE IF NOT EXISTS snomed_refsets (
    id                      BIGINT  PRIMARY KEY,           -- RF2 refset row id
    refset_id               TEXT    NOT NULL,              -- refset identifier
    referenced_component_id TEXT    NOT NULL,              -- referenced concept/description/relationship
    value                   TEXT,                          -- optional value column (varies by refset)
    is_active               BOOLEAN DEFAULT TRUE,
    effective_time          DATE    NOT NULL
);

-- ============================================================
-- Indexes for RF2 tables (performance at scale)
-- ============================================================

-- Descriptions
CREATE INDEX IF NOT EXISTS idx_snomed_desc_concept ON snomed_descriptions (concept_id);
CREATE INDEX IF NOT EXISTS idx_snomed_desc_type    ON snomed_descriptions (type_id);
CREATE INDEX IF NOT EXISTS idx_snomed_desc_lang    ON snomed_descriptions (language_code);
CREATE INDEX IF NOT EXISTS idx_snomed_desc_active  ON snomed_descriptions (is_active);
CREATE INDEX IF NOT EXISTS idx_snomed_desc_time    ON snomed_descriptions (effective_time);

-- Relationships
CREATE INDEX IF NOT EXISTS idx_snomed_rel_source   ON snomed_relationships (source_id);
CREATE INDEX IF NOT EXISTS idx_snomed_rel_dest     ON snomed_relationships (destination_id);
CREATE INDEX IF NOT EXISTS idx_snomed_rel_type     ON snomed_relationships (type_id);
CREATE INDEX IF NOT EXISTS idx_snomed_rel_active   ON snomed_relationships (is_active);
CREATE INDEX IF NOT EXISTS idx_snomed_rel_time     ON snomed_relationships (effective_time);

-- Refsets
CREATE INDEX IF NOT EXISTS idx_snomed_refset_id    ON snomed_refsets (refset_id);
CREATE INDEX IF NOT EXISTS idx_snomed_refset_ref   ON snomed_refsets (referenced_component_id);
CREATE INDEX IF NOT EXISTS idx_snomed_refset_active ON snomed_refsets (is_active);
CREATE INDEX IF NOT EXISTS idx_snomed_refset_time  ON snomed_refsets (effective_time);
