# Sample clinical notes

Synthetic notes for exercising the pipeline. No real patient data.

| File | Expected result | What it demonstrates |
|---|---|---|
| `01_pneumonia_simple.txt` | `J18.9` + CPT `71045` | The happy path. A procedure is documented, so the claim carries a real billed amount. |
| `01_pneumonia_simple.pdf` | same as above | The PDF path (digital text, so no OCR needed). |
| `02_diabetes_with_complication.txt` | `E11.42` | Specificity that IS documented — the chart records diabetic polyneuropathy, so the specific code is correct and wins. |
| `03_negation_trap.txt` | `E11.9` | Specificity that is NOT documented. The chart explicitly says "no evidence of retinopathy / neuropathy / renal disease", so the pipeline must return *without complications* and refuse to upcode. |

`02` and `03` are the pair worth showing together: same disease, and the only
thing separating a more-specific code from a less-specific one is what the
documentation actually supports. Getting that backwards in one direction is
lost revenue; in the other it is billing fraud.

Notes 2 and 3 have no billable procedure, so the estimated revenue is 0 —
their ICD rows carry a `base_reimbursement` of 0 in the seed data. Use note 1
to demonstrate the financial path.

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
