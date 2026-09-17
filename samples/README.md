# Sample clinical notes

Synthetic notes for exercising the pipeline. No real patient data.

| File | Expected result | What it demonstrates |
|---|---|---|
| `01_pneumonia_simple.txt` | `J18.9` + CPT `71045` | The happy path. A procedure is documented, so the claim carries a real billed amount. |
| `01_pneumonia_simple.pdf` | same as above | The PDF path (digital text, so no OCR needed). |
| `02_diabetes_with_complication.txt` | `E11.42` + `E11.22` + `N18.32` | Specificity that IS documented. The chart records diabetic polyneuropathy (`E11.42`) and diabetic CKD stage 3b. CKD with diabetes is coded as the combination code `E11.22` plus the stage code `N18.32`, and the stage comes from the written "stage 3b", never from the eGFR. No other diabetes type (`E10.42`, `E13.42`) is added. |
| `03_negation_trap.txt` | `E11.9` only | Specificity that is NOT documented. The chart explicitly says "no evidence of retinopathy / neuropathy / renal disease", so the pipeline must return *without complications* and refuse to upcode. |

`02` and `03` are the pair worth showing together: same disease, and the only
thing separating a more-specific code from a less-specific one is what the
documentation actually supports. Getting that backwards in one direction is
lost revenue; in the other it is billing fraud.

Notes 2 and 3 have no billable procedure, so the estimated revenue comes from
the ICD codes' seeded base reimbursement: 2,100 for note 2 (from `E11.22`;
`E11.42` and `N18.32` have none) and 1,200 for note 3 (`E11.9`). Note 1 shows
a priced CPT line (`71045`, 27.53).

A typed note works too: "Patient has Type 2 diabetes mellitus with chronic
kidney disease stage 3. eGFR is 42 mL/min." should return `E11.22` + `N18.30`
(ICD-10-CM "with" convention: diabetes and CKD are presumed linked).

## Rate limits

Groq's free tier will reject rapid consecutive calls. Leave ~20-30 seconds
between runs, or the extraction node fails and the pipeline correctly returns
a failed run rather than a fabricated result.

## Getting more realistic notes

- **MTSamples** (mtsamples.com) — thousands of free transcribed reports, no
  signup. "Discharge Summary" and "General Medicine" fit this pipeline best.
- **MIMIC-IV** (PhysioNet) — genuine de-identified ICU records; requires a
  credentialing course.
- **Synthea** — synthetic patient generator, emits FHIR bundles; good for
  volume testing.
