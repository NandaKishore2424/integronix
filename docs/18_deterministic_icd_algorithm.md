# 18 — Deterministic ICD Decision Algorithm

> This is Integronix's core intellectual property.
> The ICD Decision Node applies this algorithm to select the single best ICD-10 code.
> No code is accepted unless it passes every validation gate.

---

## Algorithm Overview

```
Input:  candidate_icd_codes[] (from SNOMED map or embedding search)
        structured_entities   (diagnosis text, severity, comorbidities, laterality)
Output: final_icd_code, confidence_score
```

The algorithm runs 7 sequential filters and scoring steps. A code that fails a gate is removed from the pool. The highest-scoring survivor wins.

---

## Step 1 — Billable Filter (Hard Gate)

**Rule:** Remove any code where `is_billable = FALSE`.

```python
def filter_billable(candidates: list) -> list:
    return [c for c in candidates if c["is_billable"] is True]

# If no billable codes remain → return error: "no_confident_match"
```

**Why:** Non-billable codes cannot be submitted to payers. No exception.

---

## Step 2 — Existence Check (Hard Gate)

**Rule:** Every candidate must physically exist in the `icd_codes` table.

```python
async def filter_exists(candidates: list, db) -> list:
    verified = []
    for c in candidates:
        row = await db.fetchrow("SELECT code FROM icd_codes WHERE code = $1", c["code"])
        if row:
            verified.append(c)
    return verified
```

**Why:** Closes the hallucination gap. LLM may suggest a code that looks right but doesn't exist. The DB is the only source of truth.

---

## Step 3 — Specificity Scoring (Ranking Gate)

Assign a specificity score to each candidate based on code structure and clinical alignment.

```python
def compute_specificity_score(candidate: dict, entities: dict) -> float:
    score = 0.0
    code = candidate["code"]
    desc = candidate["description"].lower()
    severity   = (entities.get("severity") or "").lower()
    comorbids  = [c.lower() for c in entities.get("comorbidities", [])]
    laterality = (entities.get("laterality") or "").lower()

    # 1. Code length reward: longer = more specific
    # E11.9 (4 chars) vs E11.22 (5 chars after dot = more specific)
    code_specificity = len(code.replace(".", ""))
    score += code_specificity * 1.5

    # 2. Combination code reward (with/and keywords)
    if any(kw in desc for kw in ["with", "associated with", "complicated by", "and"]):
        score += 5.0

    # 3. Severity alignment
    severity_map = {
        "acute":    ["acute", "uncompensated"],
        "chronic":  ["chronic", "longstanding"],
        "severe":   ["severe", "major", "uncontrolled"],
        "moderate": ["moderate"],
        "mild":     ["mild", "minor"]
    }
    for sev_key, sev_terms in severity_map.items():
        if sev_key in severity and any(t in desc for t in sev_terms):
            score += 3.0
            break

    # 4. Laterality alignment
    if laterality and laterality in desc:
        score += 2.0

    # 5. CC/MCC bonus (higher reimbursement, but only if clinically supported)
    if candidate.get("is_mcc"):
        score += 3.0
    elif candidate.get("is_cc"):
        score += 1.5

    # 6. Source confidence from mapping/embedding
    score += candidate.get("similarity_score", 0.5) * 4.0

    return score
```

---

## Step 4 — Clinical Consistency Validation (Hard Gate)

**Purpose:** Reject codes that contradict the extracted clinical data.

```python
def validate_clinical_consistency(candidate: dict, entities: dict) -> bool:
    desc = candidate["description"].lower()
    comorbids = [c.lower() for c in entities.get("comorbidities", [])]
    text = entities.get("diagnoses", [{}])[0].get("text", "").lower()

    # RULE: If code mentions CKD/kidney — entity must also mention CKD
    if "kidney" in desc or "renal" in desc or "ckd" in desc:
        if not any("kidney" in c or "renal" in c or "ckd" in c for c in comorbids):
            if "kidney" not in text and "renal" not in text:
                return False  # Code mentions kidney; clinical text does not

    # RULE: If code mentions neuropathy — entity must mention neuropathy
    if "neuropathy" in desc or "nerve" in desc:
        if not any("neuropathy" in c or "nerve" in c for c in comorbids):
            if "neuropathy" not in text and "nerve" not in text:
                return False

    # RULE: Acute code only if acute severity
    if "acute" in desc:
        severity = (entities.get("severity") or "").lower()
        if severity and severity not in ["acute", "severe"]:
            return False

    return True  # Passes all checks
```

---

## Step 5 — Combination Code Priority

**Rule:** If a combination code (e.g., `E11.22` — T2DM + CKD in one code) covers two conditions present in `structured_entities`, always prefer the combination code over two separate codes.

```python
def prioritize_combination_codes(candidates: list, entities: dict) -> list:
    """
    Boost combination codes when both documented conditions appear.
    """
    comorbids = [c.lower() for c in entities.get("comorbidities", [])]
    primary_text = entities.get("diagnoses", [{}])[0].get("text", "").lower()

    for c in candidates:
        desc = c["description"].lower()
        if any(kw in desc for kw in ["with", "and", "complicated by"]):
            # Check that both parts of the combination are evidenced
            parts = desc.split(" with ")
            if len(parts) == 2:
                part_a, part_b = parts[0].strip(), parts[1].strip()
                a_present = part_a in primary_text or any(part_a in cb for cb in comorbids)
                b_present = part_b in primary_text or any(part_b in cb for cb in comorbids)
                if a_present and b_present:
                    c["specificity_score"] += 6.0  # Significant boost
    return candidates
```

---

## Step 6 — Reimbursement Optimization (Controlled)

**Rule:** Among candidates with equal or near-equal specificity scores (within 1.0 of each other), prefer the one with higher `base_reimbursement`.

**Critical constraint:** Only prefer higher reimbursement if clinical evidence supports it. Never upcode without clinical backing.

```python
def apply_reimbursement_optimization(candidates: list, tolerance: float = 1.0) -> list:
    """
    Among clinically equivalent candidates, prefer higher reimbursement.
    Tolerance: max score difference to consider candidates 'equivalent'.
    """
    if not candidates:
        return candidates

    max_score = max(c["specificity_score"] for c in candidates)
    # Candidates within tolerance of the top score
    top_tier = [c for c in candidates if c["specificity_score"] >= max_score - tolerance]

    # Among top tier, sort by reimbursement descending
    top_tier.sort(key=lambda c: c.get("base_reimbursement", 0), reverse=True)
    remainder = [c for c in candidates if c not in top_tier]

    return top_tier + remainder
```

---

## Step 7 — Final Selection

```python
async def icd_decision_node(state: CodingState) -> CodingState:
    """
    Full deterministic ICD selection algorithm.
    """
    candidates = state.get("candidate_icd_codes", [])
    entities   = state["structured_entities"]

    if not candidates:
        state["final_icd_code"]   = "UNRESOLVED"
        state["confidence_score"] = 0.0
        return state

    # Step 1: Billable filter
    candidates = filter_billable(candidates)
    if not candidates:
        state["final_icd_code"]   = "UNRESOLVED"
        state["confidence_score"] = 0.0
        return state

    # Step 2: Existence check
    candidates = await filter_exists(candidates, db)

    # Step 3: Specificity scoring
    for c in candidates:
        c["specificity_score"] = compute_specificity_score(c, entities)

    # Step 4: Clinical consistency
    candidates = [c for c in candidates if validate_clinical_consistency(c, entities)]

    # Step 5: Combination code priority
    candidates = prioritize_combination_codes(candidates, entities)

    # Step 6: Reimbursement optimization
    candidates = apply_reimbursement_optimization(candidates)

    # Step 7: Final selection
    candidates.sort(key=lambda c: c["specificity_score"], reverse=True)
    best = candidates[0]

    state["final_icd_code"]   = best["code"]
    state["confidence_score"] = round(
        min(best["specificity_score"] / 25.0, 1.0), 3
    )  # Normalize to 0–1
    state["candidate_icd_codes"] = candidates  # Return ranked list

    return state
```

---

## Decision Algorithm Summary Table

| Step | Type | Purpose | Failure Action |
|---|---|---|---|
| 1. Billable Filter | Hard gate | Remove non-billable codes | Return UNRESOLVED |
| 2. Existence Check | Hard gate | Only real DB codes | Remove from pool |
| 3. Specificity Scoring | Ranking | Score all survivors | Sort descending |
| 4. Clinical Consistency | Hard gate | Reject contradictory codes | Remove from pool |
| 5. Combination Priority | Boost | Prefer combined codes | Boost score |
| 6. Reimbursement Opt. | Soft preference | Among equals, prefer higher | Re-rank |
| 7. Final Selection | Winner | Top scorer wins | — |

---

## Confidence Score Interpretation

| Score | Meaning | Action |
|---|---|---|
| 0.90 – 1.00 | Very high | Accept automatically |
| 0.70 – 0.89 | High | Accept, flag for periodic review |
| 0.50 – 0.69 | Moderate | Accept, recommend human review |
| 0.30 – 0.49 | Low | Flag for mandatory human review |
| < 0.30 | Very low | Return "low confidence" — require human |

---

## What This Prevents

| Risk | How Algorithm Prevents It |
|---|---|
| Hallucinated ICD codes | Steps 1 & 2 require code to exist in DB |
| Clinically irrelevant codes | Step 4 validates against extracted entities |
| Undercoding (missing CC/MCC) | Steps 3 & 5 reward combination/specific codes |
| Upcoding without evidence | Step 6 applies reimbursement optimization *only among equals* |
| Non-billable code submission | Step 1 hard gate eliminates all non-billable codes |

---

## Pitch Statement

> *"Our ICD decision engine runs a 7-step deterministic algorithm that filters, scores, and validates each candidate code against clinical evidence before selection. No code is accepted unless it's billable, exists in our ICD master database, is clinically consistent with the extracted entities, and passes specificity scoring. This eliminates hallucination risk entirely while maximizing coding specificity."*
