"""
This is the most critical agent in the pipeline. It's a deterministic,
rule-based engine that selects the final ICD-10 code. It does NOT use an LLM
for the final decision, ensuring accuracy, auditability, and compliance.
It follows a strict 7-step algorithm to weigh evidence and select the
most appropriate code from the candidates.
"""
from agents.graph import CodingState
from agents.node_runner import safe_node
from logger import get_logger
import re

log = get_logger(__name__)

# These keywords are used to score how specific a code is.
# For example, a code description containing "with complications" is more
# specific than one without, and its score will be boosted.
COMPLICATION_KEYWORDS = [
    r"\bwith\b",     # Using a word boundary to avoid matching "without"
    "complicated by", "chronic kidney", "acute", "stage",
    "neuropathy", "retinopathy", "nephropathy", "failure",
]
LATERALITY_KEYWORDS = ["left", "right", "bilateral", "unilateral"]
COMBINATION_KEYWORDS = [
    r"\bwith\b",
    "and", "complicated by", "associated with",
]

# If these phrases are found in the text, we apply a penalty to any
# complication-related codes, as the evidence contradicts them.
NEGATION_PHRASES = [
    "no complications", "without complications", "no evidence of",
    "no kidney disease", "no renal", "no neuropathy", "no retinopathy",
    "normal kidney function", "kidney function normal", "renal function normal",
    "without chronic", "no chronic",
]


def _kw_match(text: str, keywords: list) -> bool:
    # A helper function to check if any keywords are in the text.
    # It supports simple string matching and regular expressions for more complex cases.
    for kw in keywords:
        if kw.startswith(r"\b") or kw.startswith("("):
            if re.search(kw, text, re.IGNORECASE):
                return True
        else:
            if kw in text:
                return True
    return False


def _specificity_score(candidate: dict, entities: dict) -> float:
    # Step 3 of our algorithm: Score the specificity of a candidate code.
    code = candidate.get("code", "")
    description = candidate.get("description", "").lower()
    # Longer codes are generally more specific, so we start there.
    score = len(code) * 0.15
    diag_text = " ".join(d.get("text", "").lower() for d in entities.get("diagnoses", []))
    # If the code's description and the clinical text both mention a complication, boost the score.
    for kw in COMPLICATION_KEYWORDS:
        if _kw_match(description, [kw]) and _kw_match(diag_text, [kw]):
            score += 0.2
    return round(min(score, 1.0), 4)


def _negation_penalty(candidate: dict, entities: dict, raw_text: str = "") -> float:
    # This function applies a penalty if a code implies a complication,
    # but the clinical text explicitly says there are no complications.
    description = candidate.get("description", "").lower()
    is_complication_code = _kw_match(description, [
        r"\bwith\b", "complicated by", "chronic kidney",
        "neuropathy", "failure", "retinopathy"
    ])
    if not is_complication_code:
        return 0.0 # No penalty if it's not a complication code.

    # We check both the extracted entities and the full raw text for negation phrases.
    entity_text = " ".join(
        (d.get("text", "") + " " + d.get("evidence_text", "")).lower()
        for d in entities.get("diagnoses", [])
    )
    combined_text = (entity_text + " " + raw_text.lower()).strip()
    for phrase in NEGATION_PHRASES:
        if phrase in combined_text:
            return -0.4 # Apply a significant penalty.
    return 0.0


def _clinical_consistency_score(candidate: dict, entities: dict) -> float:
    # Step 4: Check if the terms in the ICD code's description actually
    # appear in the clinical evidence found by the LLM.
    description = candidate.get("description", "").lower()
    all_evidence = " ".join(
        d.get("evidence_text", "").lower() for d in entities.get("diagnoses", [])
    )

    # Count how many significant words in ICD description appear in evidence
    words = [w for w in description.split() if len(w) > 4]
    if not words:
        return 0.5

    matches = sum(1 for w in words if w in all_evidence)
    return round(matches / len(words), 4)


def _combination_code_priority(candidate: dict) -> float:
    """Step 5: Prefer combination codes ('with') per ICD-10 guidelines."""
    description = candidate.get("description", "").lower()
    if _kw_match(description, COMBINATION_KEYWORDS):
        return 0.2
    return 0.0


def _final_score(candidate: dict, entities: dict, raw_text: str = "") -> float:
    """
    Weighted composite:
      confidence (40%) + specificity (30%) + consistency (20%) + combination (10%) - negation penalty
    """
    confidence   = float(candidate.get("confidence", 0.85))
    specificity  = _specificity_score(candidate, entities)
    consistency  = _clinical_consistency_score(candidate, entities)
    combination  = _combination_code_priority(candidate)
    negation     = _negation_penalty(candidate, entities, raw_text)

    score = (
        confidence  * 0.40 +
        specificity * 0.30 +
        consistency * 0.20 +
        combination * 0.10 +
        negation
    )
    return round(max(0.0, min(score, 1.0)), 4)


# Add a function to prioritize codes based on clinical keywords

def _rank_by_specificity(candidates: list, raw_text: str) -> list:
    """
    Re-rank candidates based on clinical keywords like "Acute" or "Chronic".
    """
    for candidate in candidates:
        description = candidate.get("description", "").lower()
        if "acute" in raw_text.lower() and "acute" in description:
            candidate["final_score"] += 0.3  # Boost acute cases
        elif "chronic" in raw_text.lower() and "chronic" in description:
            candidate["final_score"] += 0.2  # Boost chronic cases
    return sorted(candidates, key=lambda x: x["final_score"], reverse=True)

@safe_node("icd_decision")
async def icd_decision_node(state: CodingState) -> CodingState:
    """
    LangGraph Node 6 — Deterministic ICD Decision.
    Input:  state["candidate_icd_codes"], state["structured_entities"]
    Output: state["final_icd_code"], state["confidence_score"]
    """
    session_id = str(state.get("session_id", ""))
    candidates = state.get("candidate_icd_codes", [])
    entities   = state.get("structured_entities", {})
    raw_text   = state.get("raw_text", "")   # for negation detection

    # ── Guard: no candidates ────────────────────────────────────────────────
    if not candidates:
        log.warning("icd_decision_no_candidates", session_id=session_id,
                    mapping_path=state.get("mapping_path"))
        state["final_icd_code"]   = "UNKNOWN"
        state["confidence_score"] = 0.0
        state["icd_codes"]        = []
        return state

    candidates = [c for c in candidates if c.get("is_billable", True)]
    if not candidates:
        state["final_icd_code"]   = "UNKNOWN"
        state["confidence_score"] = 0.0
        state["icd_codes"]        = []
        return state

    # ── Score every candidate ───────────────────────────────────────────────
    scored = []
    for c in candidates:
        score = _final_score(c, entities, raw_text)
        scored.append({**c, "final_score": score})

    # Apply keyword-aware re-ranking
    scored = _rank_by_specificity(scored, raw_text)

    winner = scored[0]

    state["final_icd_code"]      = winner["code"]
    state["confidence_score"]    = winner["final_score"]
    state["candidate_icd_codes"] = scored

    # ── Build multi-code list (RCM-style) ────────────────────────────────────
    def _rationale(c: dict, role: str) -> str:
        parts = []
        if c.get("is_mcc"):
            parts.append("MCC — Major Complication/Comorbidity")
        elif c.get("is_cc"):
            parts.append("CC — Complication/Comorbidity")
        mt = c.get("mapping_type", "")
        if mt == "exact":
            parts.append("exact SNOMED match")
        elif mt == "narrower":
            parts.append("more specific than SNOMED concept")
        elif mt == "approximate":
            parts.append(f"semantic match ({c.get('confidence', 0):.0%} similarity)")
        elif mt == "broader":
            parts.append("broader SNOMED match")
        if role == "secondary":
            parts.append("comorbidity candidate")
        elif role == "additional":
            parts.append("supplementary specificity code")
        if not parts:
            parts.append("billable ICD-10-CM code")
        return "; ".join(parts)

    icd_codes = [{
        "code":               winner["code"],
        "description":        winner.get("description", ""),
        "role":               "primary",
        "final_score":        winner["final_score"],
        "is_mcc":             winner.get("is_mcc", False),
        "is_cc":              winner.get("is_cc", False),
        "base_reimbursement": winner.get("base_reimbursement", 0),
        "rationale":          _rationale(winner, "primary"),
    }]

    role_labels = ["secondary", "additional"]
    role_idx = 0
    for c in scored[1:]:
        if c["final_score"] >= 0.40 and role_idx < len(role_labels):
            icd_codes.append({
                "code":               c["code"],
                "description":        c.get("description", ""),
                "role":               role_labels[role_idx],
                "final_score":        c["final_score"],
                "is_mcc":             c.get("is_mcc", False),
                "is_cc":              c.get("is_cc", False),
                "base_reimbursement": c.get("base_reimbursement", 0),
                "rationale":          _rationale(c, role_labels[role_idx]),
            })
            role_idx += 1

    state["icd_codes"] = icd_codes

    log.info(
        "icd_selected",
        session_id=session_id,
        final_icd_code=winner["code"],
        confidence_score=winner["final_score"],
        mapping_path=state.get("mapping_path"),
        candidates_evaluated=len(scored),
        multi_codes_returned=len(icd_codes),
        runner_up=scored[1]["code"] if len(scored) > 1 else None,
    )
    return state
