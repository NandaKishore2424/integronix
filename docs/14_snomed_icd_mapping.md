# 14 — SNOMED to ICD-10 Mapping Strategy

## Why This Mapping Exists

EHRs store clinical diagnoses using **SNOMED CT** concepts (rich clinical meaning).
Insurance claims require **ICD-10-CM** codes (billing representation).

**The gap between them is the mapping problem.**

```
EHR Clinical Note (SNOMED)
        │
        ▼
   Integronix Mapping Engine
        │
        ▼
   ICD-10-CM (for billing/revenue)
```

Our LLM extracts SNOMED-like structured clinical concepts.
Our mapping engine converts them to validated ICD-10 codes.

---

## 3-Layer Mapping Architecture

### Layer 1: Direct Mapping Table (Fast Path)

A pre-built lookup table of SNOMED → ICD-10 correspondences.

```sql
CREATE TABLE snomed_icd_map (
    id              SERIAL      PRIMARY KEY,
    snomed_code     TEXT        NOT NULL,
    snomed_display  TEXT,
    icd_code        TEXT        REFERENCES icd_codes(code),
    mapping_type    TEXT,       -- 'exact' | 'narrower' | 'broader' | 'approximate'
    confidence      NUMERIC,    -- 0.0 to 1.0
    notes           TEXT
);
```

**Example records:**
| snomed_code | snomed_display | icd_code | mapping_type | confidence |
|---|---|---|---|---|
| 44054006 | Diabetes mellitus type 2 | E11.9 | broader | 0.85 |
| 44054006 | Diabetes mellitus type 2 | E11.22 | narrower | 0.91 |
| 709044004 | Chronic kidney disease stage 3 | N18.3 | exact | 0.99 |
| 59621000 | Hypertension | I10 | exact | 0.99 |
| 233604007 | Pneumonia | J18.9 | broader | 0.80 |

**Source:** SNOMED International release files + NLM UMLS crosswalk

**Query example:**
```sql
SELECT icd_code, confidence, mapping_type
FROM snomed_icd_map
WHERE snomed_code = '44054006'
ORDER BY confidence DESC
LIMIT 5;
```

---

### Layer 2: Rule-Based Specificity Logic (Refinement Path)

The direct table gives candidate ICD codes.
But SNOMED often doesn't encode clinical details that ICD requires.

**Specificity rules:**

```python
def apply_specificity_rules(
    snomed_code: str,
    candidates: list[dict],
    extracted_entities: dict
) -> str:
    """
    Given a SNOMED code and candidate ICD codes,
    apply rules to select the most specific valid code.
    """
    severity = extracted_entities.get("severity")
    comorbidities = extracted_entities.get("comorbidities", [])
    
    # Diabetes specificity rules
    if snomed_code == "44054006":  # T2DM
        if "chronic kidney disease stage 3" in comorbidities:
            return "E11.22"   # T2DM with CKD → more specific
        elif "diabetic neuropathy" in comorbidities:
            return "E11.40"   # T2DM with neuropathy
        else:
            return "E11.9"    # T2DM without complications
    
    # CKD specificity rules
    if snomed_code == "709044004":  # CKD
        if "stage 3" in severity:
            return "N18.3"
        elif "stage 4" in severity:
            return "N18.4"
        elif "stage 5" in severity:
            return "N18.5"
    
    # Fallback to highest confidence candidate
    return candidates[0]["icd_code"]
```

**Purpose:** Capture CC/MCC opportunities that SNOMED alone doesn't encode.

---

### Layer 3: Semantic Similarity Fallback (When Layers 1 & 2 Fail)

If no direct SNOMED mapping exists:

1. Take SNOMED concept description (free text)
2. Generate embedding
3. Query pgvector for top 5 ICD code matches by similarity
4. Apply deterministic validation on results

This handles:
- New SNOMED codes not yet in the mapping table
- Rare clinical conditions
- Partial matches

See `15_embedding_pipeline.md` for full embedding design.

---

## Full Mapping Decision Flow

```
Extracted diagnosis text
          │
          ▼
  LLM extracts SNOMED-like concept
          │
          ▼
  Check snomed_icd_map table
          │
    ┌─────┴─────┐
  Found       Not Found
    │               │
    ▼               ▼
Specificity    Embedding similarity
  rules         search (pgvector)
    │               │
    └──────┬────────┘
           │
           ▼
    Top candidate ICD codes
           │
           ▼
    Deterministic validation:
    - is_billable = TRUE?
    - Code exists in icd_codes?
    - Specificity level matches?
           │
           ▼
    Final ICD-10 Code ✅
```

---

## Mapping Data Sources (Official)

| Source | What It Provides | URL |
|---|---|---|
| SNOMED International | SNOMED → ICD-10 map files | https://www.snomed.org/snomed-ct/releases |
| NLM UMLS | Cross-terminology mappings | https://www.nlm.nih.gov/research/umls/ |
| CMS GEMS | ICD-9 to ICD-10 general equivalence | https://www.cms.gov/medicare/coding-billing |

**For hackathon POC:**
- Manually curate 150–200 high-frequency SNOMED → ICD entries
- Cover diabetes, CKD, hypertension, pneumonia, sepsis, cardiac
- These cover ~80% of inpatient coding scenarios

---

## What to Say in Pitch

> *"Our system extracts SNOMED-like clinical concepts from documentation and maps them to ICD-10-CM billing codes using a three-layer strategy: direct lookup from our SNOMED-ICD mapping table, rule-based specificity refinement for comorbidity capture, and embedding-based semantic fallback for edge cases. Every final code is validated against our ICD master database before being accepted."*

---

## Key Differentiator for Judges

Most teams: `LLM → ICD code directly` (hallucination risk)

Integronix: `LLM → SNOMED concept → Mapping engine → ICD-10 (from DB)`

This added layer:
- Eliminates hallucinated codes
- Captures clinical precision (CC/MCC)
- Mirrors real healthcare data architecture (EHR → RCM workflow)
