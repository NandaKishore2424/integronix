# 04 — POC Scope & Features

## Scope Philosophy

> "Build a focused, working POC. Not a full enterprise product. Not over-engineered."

The goal is to **prove the concept**, not ship a product.

---

## ✅ What's IN Scope (Stage 2 POC)

### Feature 1: Document Upload
- Upload a clinical PDF (discharge summary, clinical notes)
- Extract raw text using PDF parsing
- OCR support if needed for scanned PDFs

**Output:** Raw text string stored in pipeline state

---

### Feature 2: Clinical Parser (LLM Agent)
Extract structured entities from raw text using an LLM:

```json
{
  "diagnosis": "Type 2 Diabetes with diabetic neuropathy",
  "severity": "moderate",
  "laterality": null,
  "comorbidities": ["hypertension", "chronic kidney disease"],
  "evidence_text": "Patient presents with diabetic peripheral neuropathy..."
}
```

> ⚠️ **The LLM is NEVER asked to generate ICD codes.** Only clinical entities.

---

### Feature 3: Deterministic ICD Mapping
- Maintain an internal mini ICD-10 dataset (~300–500 codes)
- Map extracted diagnosis to best matching ICD code
- Use **embedding similarity** (pgvector) for fuzzy matching
- Validate the selected code is billable

**Output:** `final_icd_code`, `confidence_score`

---

### Feature 4: Audit Comparison Mode
- User inputs a human-assigned ICD code
- System compares it with AI-suggested code
- Shows:
  - Discrepancy type (missing specificity / unsupported / exact match)
  - Supporting evidence from clinical text
  - Revenue delta (simulated)

**This is the killer demo moment.**

---

### Feature 5: Revenue Impact Simulation
- Hardcode sample reimbursement values per ICD code
- Show the dollar difference between human code and AI code
- Flag if CC/MCC was missed (increases DRG weight → more reimbursement)

> Judges will understand the concept even with mock data.

---

### Feature 6: Simple Dashboard (Frontend)
Display:

| Field | Description |
|---|---|
| Extracted Diagnosis | What the LLM parsed |
| Suggested ICD Code | Deterministic DB result |
| Confidence Score | Similarity match score |
| Human ICD Code | Entered by user |
| Revenue Delta | Simulated $ difference |
| Risk Flag | Low / Medium / High |

---

## ❌ What's OUT of Scope (Deliberately)

| Not Being Built Now | Reason |
|---|---|
| Full DRG grouper engine | Too complex, not needed for POC |
| Full NCCI rule engine | Not demonstrable in 4 weeks solo |
| Full payer-specific rule engine | Phase 4 roadmap item |
| Full 70,000 ICD-10 code import | Mini curated set is sufficient |
| Chatbot interface | Wrong format for this use case |
| UI animations / polish | Core logic first |
| Multi-tenant hospital support | Out of scope for POC |

---

## How to Explain Scope in the Pitch

> *"This prototype demonstrates deterministic ICD mapping with agentic parsing and audit comparison. Full DRG grouping, NCCI rules, and payer-specific engines are part of our Phase 4 expansion roadmap."*

This shows maturity and honest scope awareness — judges respect this.

---

## Scope Boundary Rule

Before adding any feature, ask:

> **"Does this make the demo more convincing, or does it add complexity that could break the demo?"**

If it risks demo stability → cut it.
