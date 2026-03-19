# Deterministic ICD Decision Algorithm

> The `icd_decision_node` is the intellectual core of the Integronix engine. It is a fully deterministic, rule-based algorithm responsible for selecting the final, most accurate ICD code. By deliberately avoiding a final-step LLM "opinion," we ensure every decision is auditable, compliant, and based on a traceable set of rules.

---

## 1. Algorithm Overview

The node receives a list of `candidate_icd_codes` from one of the upstream paths (WHO API, SNOMED mapping, or embedding search). It enriches, scores, and ranks these candidates through a multi-step process to select a winner.

**Input:**
- `candidate_icd_codes[]`: A list of potential ICD codes.
- `structured_entities`: The FHIR-like JSON from the `clinical_extractor` node.
- `raw_text`: The full, original clinical note.

**Output:**
- `final_icd_code`: The single best ICD code selected.
- `confidence_score`: The final calculated confidence in the selection.
- `icd_codes[]`: A list of codes for the final report, including primary, secondary, and additional codes.
- `decision_trace`: An audit object detailing the logic path taken.

---

## 2. Step 1: Candidate Augmentation (Robustness)

Before scoring begins, the node checks if the candidate pool is sufficient.

-   **Rule**: If the initial list of candidates is empty or has fewer than 3 codes, the system triggers a fallback mechanism.
-   **Action**: It calls the `icd_provider` service, which dynamically queries the appropriate data source (internal ICD-10 DB or external WHO ICD-11 API, based on `org_settings`) using the diagnosis text.
-   **Result**: The new candidates are merged with any existing ones, ensuring the decision engine always has a rich set of options to evaluate. The `mapping_path` is updated to `"provider_fallback"` or `"provider_augmented"` to trace this action.

---

## 3. Step 2: Hard Gate - Billable Filter

-   **Rule**: Remove any candidate code where `is_billable = FALSE`.
-   **Justification**: This is a non-negotiable first step. Non-billable codes are category headers (e.g., `E11`) and cannot be used for billing. The system must only select codes that are valid for submission.

---

## 4. Step 3: The Scoring Gauntlet

Every surviving candidate is passed through a series of scoring functions. The results are combined into a `final_score`.

### A. Specificity Score (`_specificity_score`)
-   **Purpose**: To reward codes that are more clinically specific.
-   **Metrics**:
    -   **Code Length**: Longer codes (e.g., `I21.4` vs. `I21`) receive a higher score.
    -   **Keyword Matching**: The score is boosted if keywords from our curated `COMPLICATION_KEYWORDS` list (e.g., "with," "acute," "neuropathy") appear in *both* the ICD code's description and the clinical text from the `structured_entities`.

### B. Clinical Consistency Score (`_clinical_consistency_score`)
-   **Purpose**: To measure how well the code's description is supported by the clinical evidence.
-   **Logic**: It tokenizes the ICD description into significant words (length > 4) and calculates the percentage of those words that appear in the `evidence_text` provided by the `clinical_extractor` node. A higher percentage yields a higher score.

### C. Combination Code Priority (`_combination_code_priority`)
-   **Purpose**: To adhere to ICD-10 guidelines that prefer single "combination codes" over multiple individual codes.
-   **Logic**: If a code's description contains keywords like "with," "and," or "associated with," it receives a score boost.

### D. Negation Penalty (`_negation_penalty`)
-   **Purpose**: To prevent the selection of a complication code when the text explicitly denies it.
-   **Logic**: If a candidate is a "complication code" (e.g., "Diabetes with neuropathy"), the function searches the full `raw_text` for phrases from our `NEGATION_PHRASES` list (e.g., "no complications," "no evidence of neuropathy"). If a negation is found, a significant penalty is applied to the score.

---

## 5. Step 4: Final Score Calculation & Ranking

The individual scores are combined into a single `final_score` using a weighted formula that prioritizes different factors:

`score = (confidence * 0.4) + (specificity * 0.3) + (consistency * 0.2) + (combination * 0.1) + negation_penalty`

-   `confidence`: The initial score from the upstream node (e.g., the similarity score from an embedding search).

After this initial calculation, two final adjustments are made:

1.  **Penalize Unspecified Codes**: Any code ending in `.9`, `.90`, or `.0` (indicating it's "unspecified") receives a score penalty if the clinical text contains specific keywords that suggest a more precise code is available.
2.  **Apply Gold Standard Keywords**: The system checks the text for a curated list of `GOLD_STANDARD_KEYWORDS` (e.g., "NSTEMI"). If a keyword is found and a candidate code is an exact match for that keyword's standard code (e.g., `I21.4`), its score is immediately boosted to `0.98`, making it the almost certain winner.

Finally, all candidates are sorted in descending order by `final_score`.

---

## 6. Step 5: The Decision & Multi-Code Output

-   **Winner Selection**: The candidate at the top of the ranked list (with the highest `final_score`) is selected as the `final_icd_code`.

-   **Multi-Code Generation**: The system does not stop there. It generates a list of codes for the final report, mimicking a human coder's output:
    1.  The winning code is assigned the `role: "primary"`.
    2.  Other high-scoring candidates (`final_score >= 0.40`) are included with roles like `"secondary"` or `"additional"`.
    3.  A detailed `rationale` is generated for each code, explaining why it was chosen (e.g., "MCC — Major Complication/Comorbidity," "exact SNOMED match," "semantic match").

This deterministic, multi-faceted algorithm ensures that the final code selection is not just a guess, but a defensible and clinically sound conclusion based on a weighted analysis of all available evidence.


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
