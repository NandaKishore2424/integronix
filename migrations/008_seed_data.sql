-- ============================================================
-- Migration 008: Seed Data
-- Minimal but correct data to verify schema and test the pipeline.
-- ICD codes chosen to cover: diabetes, CKD, combination codes, sepsis.
-- ============================================================

-- ── Step 1: ICD-10 Codes (10 billable codes) ──────────────────────────────
INSERT INTO icd_codes
    (code,    description,                                                       chapter,          category,              is_billable, is_cc,  is_mcc, base_reimbursement)
VALUES
    ('E11.9',  'Type 2 diabetes mellitus without complications',                 'Endocrine',      'Diabetes',            true,        false,  false,  1200),
    ('E11.22', 'Type 2 diabetes mellitus with diabetic chronic kidney disease',  'Endocrine',      'Diabetes',            true,        true,   false,  2100),
    ('E11.40', 'Type 2 diabetes mellitus with diabetic neuropathy, unspecified', 'Endocrine',      'Diabetes',            true,        true,   false,  1900),
    ('N18.3',  'Chronic kidney disease, stage 3',                                'Genitourinary',  'CKD',                 true,        true,   false,  1500),
    ('N18.4',  'Chronic kidney disease, stage 4',                                'Genitourinary',  'CKD',                 true,        true,   false,  1750),
    ('I10',    'Essential (primary) hypertension',                               'Circulatory',    'HTN',                 true,        false,  false,   900),
    ('J18.9',  'Pneumonia, unspecified organism',                                'Respiratory',    'Pneumonia',           true,        false,  false,  1800),
    ('J96.00', 'Acute respiratory failure, unspecified',                         'Respiratory',    'Respiratory failure', true,        false,  true,   3500),
    ('A41.9',  'Sepsis, unspecified organism',                                   'Infectious',     'Sepsis',              true,        false,  true,   5000),
    ('I50.9',  'Heart failure, unspecified',                                     'Circulatory',    'Heart failure',       true,        false,  false,  2400);

-- ── Step 2: SNOMED Concepts (5 clinical concepts) ─────────────────────────
INSERT INTO snomed_concepts
    (snomed_code,  description,                      semantic_tag,  hierarchy)
VALUES
    ('44054006',   'Diabetes mellitus type 2',        '(disorder)',  'Clinical finding'),
    ('709044004',  'Chronic kidney disease stage 3',  '(disorder)',  'Clinical finding'),
    ('73211009',   'Diabetes mellitus',               '(disorder)',  'Clinical finding'),
    ('59621000',   'Essential hypertension',          '(disorder)',  'Clinical finding'),
    ('233604007',  'Pneumonia',                       '(disorder)',  'Clinical finding');

-- ── Step 3: SNOMED → ICD Crosswalk (6 mappings) ───────────────────────────
-- These represent the deterministic backbone used by snomed_icd_map node
INSERT INTO snomed_icd_map
    (snomed_code,  icd_code,  mapping_type,  confidence,  is_primary,  source,    notes)
VALUES
    -- Diabetes type 2 → three valid ICD mappings at different specificity levels
    ('44054006',   'E11.9',   'broader',     0.85,        false,       'manual',  'ICD less specific — no complication mentioned'),
    ('44054006',   'E11.22',  'narrower',    0.91,        true,        'manual',  'Preferred when CKD comorbidity is documented'),
    ('44054006',   'E11.40',  'narrower',    0.82,        false,       'manual',  'Use when neuropathy is documented'),
    -- CKD stage 3 → exact match
    ('709044004',  'N18.3',   'exact',       0.99,        true,        'manual',  'SNOMED and ICD are semantically equivalent'),
    -- Hypertension → exact match
    ('59621000',   'I10',     'exact',       0.99,        true,        'manual',  'SNOMED and ICD are semantically equivalent'),
    -- Pneumonia → broader (ICD is less specific than general SNOMED pneumonia)
    ('233604007',  'J18.9',   'broader',     0.80,        true,        'manual',  'Best ICD match for unspecified pneumonia');

-- ── Verification ──────────────────────────────────────────────────────────
-- After running this file, verify with:
--
-- 1. SELECT COUNT(*) FROM icd_codes;          → 10
-- 2. SELECT COUNT(*) FROM snomed_concepts;    → 5
-- 3. SELECT COUNT(*) FROM snomed_icd_map;     → 6
--
-- 4. Full crosswalk join:
-- SELECT sc.description, sim.mapping_type, sim.confidence, ic.code, ic.description
-- FROM snomed_icd_map sim
-- JOIN snomed_concepts sc ON sc.snomed_code = sim.snomed_code
-- JOIN icd_codes ic ON ic.code = sim.icd_code
-- ORDER BY sim.confidence DESC;
