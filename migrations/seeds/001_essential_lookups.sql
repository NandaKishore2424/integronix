-- ============================================================
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
  ('233604007',  'Pneumonia',                       '(disorder)',  'Clinical finding'),
  ('57054005',   'Non-ST elevation myocardial infarction', '(disorder)', 'Clinical finding'),
  ('441481004',  'Acute systolic heart failure',    '(disorder)',  'Clinical finding'),
  ('53084003',   'Pneumonia caused by Klebsiella',  '(disorder)',  'Clinical finding');

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
-- ============================================================
-- Migration 009: Expanded ICD Seed Data (~60 high-frequency codes)
-- Covers: Endocrine, Circulatory, Respiratory, Gastro,
--         Neuro, MSK, Mental Health, Symptoms, Infectious
-- ============================================================

-- ── Endocrine ─────────────────────────────────────────────────────────────────
INSERT INTO icd_codes (code, description, chapter, category, is_billable, is_cc, is_mcc, base_reimbursement)
VALUES
  ('E10.9',  'Type 1 diabetes mellitus without complications',                    'Endocrine', 'Diabetes T1',    true, false, false, 1300),
  ('E11.65', 'Type 2 diabetes mellitus with hyperglycemia',                       'Endocrine', 'Diabetes',       true, false, false, 1402),
  ('E11.51', 'Type 2 diabetes mellitus with diabetic peripheral angiopathy',      'Endocrine', 'Diabetes',       true, true,  false, 2000),
  ('E78.5',  'Hyperlipidemia, unspecified',                                       'Endocrine', 'Lipid',          true, false, false,  700),
  ('E78.00', 'Pure hypercholesterolemia, unspecified',                            'Endocrine', 'Lipid',          true, false, false,  750),
  ('E11.641','Type 2 diabetes with hypoglycemia with coma',                       'Endocrine', 'Diabetes',       true, false, true,  3200),
  ('E03.9',  'Hypothyroidism, unspecified',                                       'Endocrine', 'Thyroid',        true, false, false,  800),
  ('E05.90', 'Thyrotoxicosis, unspecified, without thyrotoxic crisis',            'Endocrine', 'Thyroid',        true, false, false,  900)
ON CONFLICT (code) DO NOTHING;

-- ── Circulatory ───────────────────────────────────────────────────────────────
INSERT INTO icd_codes (code, description, chapter, category, is_billable, is_cc, is_mcc, base_reimbursement)
VALUES
  ('I25.10', 'Atherosclerotic heart disease of native coronary artery',           'Circulatory', 'CAD',           true, true,  false, 2500),
  ('I50.32', 'Chronic diastolic (congestive) heart failure',                      'Circulatory', 'Heart failure', true, true,  false, 2600),
  ('I50.22', 'Chronic systolic (congestive) heart failure',                       'Circulatory', 'Heart failure', true, true,  false, 2700),
  ('I50.21', 'Acute systolic (congestive) heart failure',                         'Circulatory', 'Heart failure', true, true,  true,  3200),
  ('I21.9',  'Acute myocardial infarction, unspecified',                          'Circulatory', 'MI',            true, false, true,  5500),
  ('I21.4',  'Non-ST elevation (NSTEMI) myocardial infarction',                   'Circulatory', 'MI',            true, false, true,  5600),
  ('I48.91', 'Unspecified atrial fibrillation',                                   'Circulatory', 'Arrhythmia',    true, true,  false, 2000),
  ('I63.9',  'Cerebral infarction, unspecified',                                  'Circulatory', 'Stroke',        true, false, true,  6000),
  ('I82.401','Acute thrombosis of unspecified deep veins of right lower extremity','Circulatory','DVT',           true, true,  false, 1800),
  ('I87.2',  'Venous insufficiency (chronic)(peripheral)',                         'Circulatory', 'Venous',        true, false, false,  850),
  ('I27.20', 'Pulmonary hypertension, unspecified',                               'Circulatory', 'PHT',           true, true,  false, 2200)
ON CONFLICT (code) DO NOTHING;

-- ── Respiratory ───────────────────────────────────────────────────────────────
INSERT INTO icd_codes (code, description, chapter, category, is_billable, is_cc, is_mcc, base_reimbursement)
VALUES
  ('J44.9',  'Chronic obstructive pulmonary disease, unspecified',                'Respiratory', 'COPD',          true, true,  false, 1900),
  ('J44.1',  'COPD with acute exacerbation',                                      'Respiratory', 'COPD',          true, false, true,  3800),
  ('J45.909','Unspecified asthma, uncomplicated',                                  'Respiratory', 'Asthma',        true, false, false, 1100),
  ('J45.51', 'Severe persistent asthma with acute exacerbation',                  'Respiratory', 'Asthma',        true, false, true,  3500),
  ('J22',    'Unspecified acute lower respiratory infection',                      'Respiratory', 'LRTI',          true, false, false, 1200),
  ('J15.9',  'Unspecified bacterial pneumonia',                                   'Respiratory', 'Pneumonia',     true, true,  false, 2400),
  ('J15.0',  'Pneumonia due to Klebsiella pneumoniae',                             'Respiratory', 'Pneumonia',     true, true,  false, 2500),
  ('J81.0',  'Acute pulmonary edema',                                             'Respiratory', 'Pulmonary',     true, false, true,  4200)
ON CONFLICT (code) DO NOTHING;

-- ── Gastroenterology ─────────────────────────────────────────────────────────
INSERT INTO icd_codes (code, description, chapter, category, is_billable, is_cc, is_mcc, base_reimbursement)
VALUES
  ('K21.9',  'Gastro-esophageal reflux disease without esophagitis',             'Digestive', 'GERD',           true, false, false,  650),
  ('K21.0',  'Gastro-esophageal reflux disease with esophagitis',                'Digestive', 'GERD',           true, false, false,  850),
  ('K52.9',  'Noninfective gastroenteritis and colitis, unspecified',             'Digestive', 'GI',             true, false, false,  700),
  ('K74.60', 'Unspecified cirrhosis of liver',                                   'Digestive', 'Liver',          true, true,  false, 3000),
  ('K80.20', 'Calculus of gallbladder without cholecystitis',                    'Digestive', 'Gallbladder',    true, false, false,  900),
  ('K57.30', 'Diverticulosis of large intestine without perforation',             'Digestive', 'Bowel',          true, false, false,  750),
  ('K92.1',  'Melena',                                                            'Digestive', 'GI bleed',       true, false, false, 1500)
ON CONFLICT (code) DO NOTHING;

-- ── Neurology ─────────────────────────────────────────────────────────────────
INSERT INTO icd_codes (code, description, chapter, category, is_billable, is_cc, is_mcc, base_reimbursement)
VALUES
  ('G62.9',  'Polyneuropathy, unspecified',                                       'Neuro', 'Neuropathy',         true, false, false,  950),
  ('G40.909','Epilepsy, unspecified, not intractable, without status epilepticus', 'Neuro', 'Epilepsy',          true, false, false, 1200),
  ('G43.909','Migraine, unspecified, not intractable, without status migrainosus', 'Neuro', 'Migraine',          true, false, false,  700),
  ('G20',    'Parkinson disease',                                                  'Neuro', 'PD',                true, true,  false, 2000),
  ('G35',    'Multiple sclerosis',                                                 'Neuro', 'MS',                true, true,  false, 2400),
  ('G89.29', 'Other chronic pain',                                                 'Neuro', 'Pain',              true, false, false,  600)
ON CONFLICT (code) DO NOTHING;

-- ── Musculoskeletal ───────────────────────────────────────────────────────────
INSERT INTO icd_codes (code, description, chapter, category, is_billable, is_cc, is_mcc, base_reimbursement)
VALUES
  ('M54.5',  'Low back pain',                                                     'MSK', 'Back pain',           true, false, false,  600),
  ('M54.51', 'Vertebrogenic low back pain',                                        'MSK', 'Back pain',           true, false, false,  700),
  ('M17.9',  'Osteoarthritis of knee, unspecified',                               'MSK', 'Arthritis',           true, false, false,  800),
  ('M06.9',  'Rheumatoid arthritis, unspecified',                                 'MSK', 'Arthritis',           true, true,  false, 1600),
  ('M81.0',  'Age-related osteoporosis without current pathological fracture',    'MSK', 'Bone',                true, false, false,  700),
  ('M79.3',  'Panniculitis, unspecified',                                         'MSK', 'MSK',                 true, false, false,  500)
ON CONFLICT (code) DO NOTHING;

-- ── Mental Health ─────────────────────────────────────────────────────────────
INSERT INTO icd_codes (code, description, chapter, category, is_billable, is_cc, is_mcc, base_reimbursement)
VALUES
  ('F32.9',  'Major depressive disorder, single episode, unspecified',            'Mental', 'Depression',        true, false, false,  900),
  ('F33.9',  'Major depressive disorder, recurrent, unspecified',                 'Mental', 'Depression',        true, false, false,  950),
  ('F41.1',  'Generalized anxiety disorder',                                      'Mental', 'Anxiety',           true, false, false,  750),
  ('F41.9',  'Anxiety disorder, unspecified',                                     'Mental', 'Anxiety',           true, false, false,  700),
  ('F10.10', 'Alcohol abuse, uncomplicated',                                      'Mental', 'Substance',         true, false, false, 1100),
  ('F20.9',  'Schizophrenia, unspecified',                                        'Mental', 'Psychosis',         true, false, false, 2500),
  ('F31.9',  'Bipolar disorder, unspecified',                                     'Mental', 'Mood',              true, false, false, 1800)
ON CONFLICT (code) DO NOTHING;

-- ── Symptoms / Unspecified ────────────────────────────────────────────────────
INSERT INTO icd_codes (code, description, chapter, category, is_billable, is_cc, is_mcc, base_reimbursement)
VALUES
  ('R07.9',  'Chest pain, unspecified',                                           'Symptoms', 'Chest pain',      true, false, false,  500),
  ('R51',    'Headache, unspecified',                                              'Symptoms', 'Headache',        true, false, false,  400),
  ('R05.9',  'Cough, unspecified',                                                 'Symptoms', 'Cough',           true, false, false,  350),
  ('R10.9',  'Unspecified abdominal pain',                                         'Symptoms', 'Abd pain',        true, false, false,  450),
  ('R55',    'Syncope and collapse',                                               'Symptoms', 'Syncope',         true, false, false,  700),
  ('R41.3',  'Other amnesia',                                                      'Symptoms', 'Memory',          true, false, false,  600)
ON CONFLICT (code) DO NOTHING;

-- ── Infectious ────────────────────────────────────────────────────────────────
INSERT INTO icd_codes (code, description, chapter, category, is_billable, is_cc, is_mcc, base_reimbursement)
VALUES
  ('B02.9',  'Zoster without complications',                                      'Infectious', 'Viral',         true, false, false,  800),
  ('L03.90', 'Cellulitis, unspecified',                                           'Skin', 'Skin infection',      true, false, false,  900),
  ('N39.0',  'Urinary tract infection, site not specified',                       'Genitourinary', 'UTI',        true, false, false,  700),
  ('N18.30', 'Chronic kidney disease, stage 3, unspecified',                      'Genitourinary', 'CKD',        true, true,  false, 1600),
  ('N18.5',  'Chronic kidney disease, stage 5',                                   'Genitourinary', 'CKD',        true, true,  false, 2200),
  ('N18.6',  'End stage renal disease',                                           'Genitourinary', 'ESRD',       true, false, true,  4500)
ON CONFLICT (code) DO NOTHING;

-- ── Additional SNOMED Concepts (for embedding fallback tests) ─────────────────
-- NOTE: These are added WITHOUT snomed_icd_map entries intentionally
--       so that the embedding fallback (Node 5) triggers for these conditions.
INSERT INTO snomed_concepts (snomed_code, description, semantic_tag, hierarchy)
VALUES
  ('279039007', 'Low back pain',                       '(disorder)', 'Clinical finding'),
  ('57676002',  'Joint pain',                          '(finding)',  'Clinical finding'),
  ('267036007', 'Dyspnea',                             '(finding)',  'Clinical finding'),
  ('62315008',  'Diarrhea',                            '(finding)',  'Clinical finding'),
  ('35489007',  'Depressive disorder',                 '(disorder)', 'Clinical finding'),
  ('197480006', 'Anxiety disorder',                    '(disorder)', 'Clinical finding'),
  ('73430006',  'Sleep disorder',                      '(disorder)', 'Clinical finding'),
  ('22298006',  'Myocardial infarction',               '(disorder)', 'Clinical finding'),
  ('13645005',  'Chronic obstructive lung disease',    '(disorder)', 'Clinical finding'),
  ('195967001', 'Asthma',                              '(disorder)', 'Clinical finding'),
  ('413839001', 'Chronic lung disease',                '(disorder)', 'Clinical finding'),
  ('40275004',  'Contact dermatitis',                  '(disorder)', 'Clinical finding')
ON CONFLICT (snomed_code) DO NOTHING;

-- ── Additional SNOMED → ICD mappings for new high-frequency conditions ────────
INSERT INTO snomed_icd_map (snomed_code, icd_code, mapping_type, confidence, is_primary, source, notes)
VALUES
  ('22298006',  'I21.9', 'exact',    0.98, true,  'manual', 'MI to acute MI unspecified'),
  ('13645005',  'J44.9', 'exact',    0.97, true,  'manual', 'COPD to unspecified COPD'),
  ('195967001', 'J45.909','exact',   0.96, true,  'manual', 'Asthma to unspecified asthma'),
  ('35489007',  'F32.9', 'broader',  0.88, true,  'manual', 'Depressive disorder to single episode'),
  ('197480006', 'F41.9', 'broader',  0.87, true,  'manual', 'Anxiety disorder to unspecified anxiety'),
  ('57054005',  'I21.4', 'exact',    0.99, true,  'manual', 'NSTEMI Specific'),
  ('441481004', 'I50.21','exact',    0.99, true,  'manual', 'Acute Systolic HF'),
  ('53084003',  'J15.0', 'exact',    0.99, true,  'manual', 'Klebsiella Pathogen'),
  ('709044004', 'N18.30','exact',    0.95, false, 'manual', 'CKD Stage 3 Unspecified')
  -- Note: Low back pain (279039007) intentionally has NO mapping → triggers embedding fallback
ON CONFLICT (snomed_code, icd_code) DO NOTHING;
