-- migration: 011_fix_snomed_icd_map_schema.sql
-- Description: Standardizes bridge table column names and seeds high-value demo data.

-- 1. Correct Column Naming (DDL)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'snomed_icd_map'
          AND column_name = 'icd_code'
    ) THEN
        ALTER TABLE "public"."snomed_icd_map" RENAME COLUMN "icd_code" TO "icd_code_id";
    END IF;
END $$;

-- 2. Ensure Unique Constraint on ICD codes for foreign key integrity
ALTER TABLE "public"."icd_codes" DROP CONSTRAINT IF EXISTS "icd_codes_code_unique";
ALTER TABLE "public"."icd_codes" ADD CONSTRAINT "icd_codes_code_unique" UNIQUE ("code");

-- 3. Update Foreign Key Relationship
ALTER TABLE "public"."snomed_icd_map"
DROP CONSTRAINT IF EXISTS "snomed_icd_map_icd_code_id_fkey",
ADD CONSTRAINT "snomed_icd_map_icd_code_id_fkey"
FOREIGN KEY ("icd_code_id")
REFERENCES "public"."icd_codes" ("code")
ON UPDATE CASCADE ON DELETE CASCADE;

-- 4. Clean Slate Seeding (DML)
TRUNCATE TABLE "public"."snomed_icd_map" RESTART IDENTITY;

-- 4a. Ensure SNOMED concepts exist (FK prerequisite)
INSERT INTO "public"."snomed_concepts"
("snomed_code", "description", "semantic_tag", "hierarchy")
VALUES
('57054005', 'Non-ST elevation myocardial infarction', '(disorder)', 'Clinical finding'),
('441481004', 'Acute systolic heart failure', '(disorder)', 'Clinical finding'),
('53084003', 'Pneumonia caused by Klebsiella', '(disorder)', 'Clinical finding'),
('44054006', 'Diabetes mellitus type 2', '(disorder)', 'Clinical finding'),
('709044004', 'Chronic kidney disease stage 3', '(disorder)', 'Clinical finding')
ON CONFLICT ("snomed_code") DO NOTHING;

-- 4b. Ensure ICD codes exist (FK prerequisite)
INSERT INTO "public"."icd_codes"
("code", "description", "chapter", "category", "is_billable", "is_cc", "is_mcc", "base_reimbursement")
VALUES
('I21.4', 'Non-ST elevation (NSTEMI) myocardial infarction', 'Circulatory', 'MI', true, false, true, 5600),
('I50.21', 'Acute systolic (congestive) heart failure', 'Circulatory', 'Heart failure', true, true, true, 3200),
('J15.0', 'Pneumonia due to Klebsiella pneumoniae', 'Respiratory', 'Pneumonia', true, true, false, 2500),
('E11.22', 'Type 2 diabetes mellitus with diabetic chronic kidney disease', 'Endocrine', 'Diabetes', true, true, false, 2100),
('N18.3', 'Chronic kidney disease, stage 3', 'Genitourinary', 'CKD', true, true, false, 1500)
ON CONFLICT ("code") DO NOTHING;

INSERT INTO "public"."snomed_icd_map"
("snomed_code", "icd_code_id", "mapping_type", "confidence", "is_primary", "notes", "source")
VALUES
-- Key Demonstration Mappings
('57054005', 'I21.4', 'exact', 0.99, true, 'NSTEMI Mapping', 'manual'),
('441481004', 'I50.21', 'exact', 0.99, true, 'Acute Systolic HF (MCC)', 'manual'),
('53084003', 'J15.0', 'exact', 0.99, true, 'Klebsiella Pneumonia', 'manual'),
('44054006', 'E11.22', 'narrower', 0.91, true, 'Diabetes with CKD', 'manual'),
('709044004', 'N18.3', 'exact', 0.99, true, 'CKD Stage 3', 'manual');
