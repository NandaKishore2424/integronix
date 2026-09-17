"""
This is the most critical agent in the pipeline. It's a deterministic,
rule-based engine that selects the final ICD-10 code. It does NOT use an LLM
for the final decision, ensuring accuracy, auditability, and compliance.
It follows a strict 7-step algorithm to weigh evidence and select the
most appropriate code from the candidates.
"""
from agents.graph import CodingState
from agents.icd_embedding import find_icd_candidates_by_vector
from agents.node_runner import safe_node
from database import select
from logger import get_logger
from services.icd_provider import get_icd_results
from services.icd_service import query_tokens
import re

log = get_logger(__name__)

# These keywords are used to score how specific a code is.
# For example, a code description containing "with complications" is more
# specific than one without, and its score will be boosted.
# Words that describe coding metadata rather than clinical findings. They are
# never "distinguishing" — a note cannot be expected to contain "unspecified".
META_WORDS = {
    "unspecified", "specified", "other", "organism", "elsewhere",
    "classified", "without", "disease", "disorder", "condition",
    "encounter", "initial", "subsequent", "sequela", "personal", "history",
}


def _description_tokens(description: str) -> list[str]:
    return [w for w in re.findall(r"[a-z]+", description.lower()) if len(w) > 4]


def _distinguishing_support(candidate: dict, entities: dict, raw_text: str) -> float:
    """
    Fraction of the code's distinguishing clinical terms the chart supports.

    ICD-10-CM guideline: code to the highest level of specificity SUPPORTED BY
    the documentation. "Desquamative interstitial pneumonia" (J84.117) must not
    outrank plain "Pneumonia, unspecified organism" (J18.9) for a note that
    never mentions desquamative or interstitial — a longer code is only more
    correct when the chart actually documents what makes it specific.
    """
    tokens = [w for w in _description_tokens(candidate.get("description", ""))
              if w not in META_WORDS]
    if not tokens:
        return 1.0
    hay = (raw_text or "").lower() + " " + " ".join(
        (d.get("text") or "").lower() + " " + (d.get("evidence_text") or "").lower()
        for d in entities.get("diagnoses", [])
    )
    return sum(1 for w in tokens if w in hay) / len(tokens)


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

# Add a dictionary for "Gold Standard" keyword-to-code mappings
GOLD_STANDARD_KEYWORDS = {
    "nstemi": "I21.4",
    "non-st elevation": "I21.4",
    "stemi": "I21.3",  # Location-specific logic can be added if needed
    "acute systolic heart failure": "I50.21",
    "acute on chronic systolic heart failure": "I50.23",
}

# Add a function to penalize unspecified codes
def _penalize_unspecified_codes(candidates: list, raw_text: str) -> list:
    """
    Penalize codes ending in .9, .90, or .0 if specific descriptors are present in the clinical text.
    """
    for candidate in candidates:
        code = candidate.get("code", "")
        description = candidate.get("description", "").lower()
        if code.endswith(".9") or code.endswith(".90") or code.endswith(".0"):
            if any(keyword in raw_text.lower() for keyword in GOLD_STANDARD_KEYWORDS.keys()):
                candidate["final_score"] -= 0.3  # Apply penalty for unspecified codes
    return candidates

# Add a function to handle "Gold Standard" keyword matches
def _apply_gold_standard_keywords(candidates: list, raw_text: str) -> list:
    """
    Check for Gold Standard keywords in the clinical text and prioritize exact matches.
    """
    for candidate in candidates:
        for keyword, exact_code in GOLD_STANDARD_KEYWORDS.items():
            if keyword in raw_text.lower():
                if candidate.get("code") == exact_code:
                    candidate["final_score"] = 0.98  # Set high confidence for exact matches
    return sorted(candidates, key=lambda x: x["final_score"], reverse=True)

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


def _specificity_score(candidate: dict, entities: dict, raw_text: str = "") -> float:
    # Step 3: Score the specificity of a candidate code — but specificity must
    # be EARNED by the documentation. Length alone once let J84.117
    # ("Desquamative interstitial pneumonia", 7 chars) outrank J18.9 for a
    # plain community-acquired pneumonia note, purely because len("J84.117")
    # * 0.15 maxed the score. Unsupported specificity is upcoding.
    code = candidate.get("code", "")
    description = candidate.get("description", "").lower()
    base = min(len(code) * 0.15, 1.0)
    support = _distinguishing_support(candidate, entities, raw_text)
    score = base * (0.35 + 0.65 * support)
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

    # Count how many significant CLINICAL words of the description appear in
    # the evidence. Meta words ("unspecified", "organism") are excluded — they
    # describe the code, not the patient, and counting them punished exactly
    # the codes that should win when documentation is non-specific.
    words = [w for w in _description_tokens(description) if w not in META_WORDS]
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
    try:
        confidence   = float(candidate.get("confidence", 0.85))
        specificity  = _specificity_score(candidate, entities, raw_text)
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
    except Exception as e:
        log.error("final_score_error", error=str(e), candidate=candidate)
        return 0.0  # Default to 0.0 if scoring fails


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


# ── Which diagnoses a candidate codes ────────────────────────────────────────
# Every candidate carries "covers": indices into structured_entities
# ["diagnoses"]. The WHO, SNOMED and vector nodes only ever look at
# diagnoses[0], so their candidates cover [0]. Codes are chosen per
# diagnosis. Selection used to be "every runner-up scoring >= 0.40", and a
# runner-up is almost always another way to code the SAME diagnosis: a CKD
# note came back as E11.9 plus a retinopathy code, and a polyneuropathy
# note as type 2 plus type 1 plus "other specified" diabetes.

SECONDARY_MIN_SCORE = 0.40
# Share of the words a secondary code adds that the diagnosis line must document.
MIN_DOCUMENTED_DETAIL = 0.5
MAX_ICD_CODES = 12            # an 837P claim carries at most 12 diagnosis codes
MAX_DIAGNOSES_LOOKED_UP = 5   # bounds the extra searches one note can trigger
CONVENTION_SOURCE = "icd_convention"

# Joining words. META_WORDS already covers coding boilerplate.
_DETAIL_STOPWORDS = frozenset({
    "with", "and", "the", "for", "due", "from", "not", "nos", "nec", "type",
    "stage", "use", "any", "has", "was", "are", "but", "into", "than",
})
# ICD descriptions say "diabetic X" where notes say "diabetes with X".
_DETAIL_ALIASES = {"diabetic": "diabetes"}
_NO_EVIDENCE_TEXT = "evidence not found."   # extraction_service placeholder

# A diagnosis line that is itself a denial ("No evidence of renal disease",
# "Pneumonia ruled out") codes nothing. A line that merely CONTAINS a denial
# ("diabetes, no retinopathy") is still a diagnosis.
_NEGATED_DIAGNOSIS_RE = re.compile(
    r"^\s*(?:no|not|without|denies|denied|negative for|ruled out|rule out|r/o|absence of|free of)\b"
    r"|\bruled out[\s.]*$"
)
# Diabetes shorthand; says nothing a combination code does not already say.
_DIABETES_SHORTHAND = frozenset({"t1dm", "t2dm", "iddm", "niddm"})


def _covers(candidate: dict) -> list[int]:
    return list(candidate.get("covers") or [0])


def _with_covers(candidate: dict, covers: list[int]) -> dict:
    if candidate.get("covers"):
        return candidate
    return {**candidate, "covers": list(covers)}


def _normalize_text(text: str) -> str:
    text = re.sub(r"[^a-z0-9\s]+", " ", (text or "").lower())
    return re.sub(r"\s+", " ", text).strip()


def _detail_tokens(text: str, strip_modifiers: bool = True) -> set[str]:
    """
    The clinical words of a code description or a piece of note text.

    In a description, parenthesised words are ICD "nonessential modifiers"
    ("Essential (primary) hypertension"): the code applies whether or not the
    note repeats them, so they are not detail the note must document.
    """
    if strip_modifiers:
        text = re.sub(r"\([^)]*\)", " ", text or "")
    tokens = set()
    for token in query_tokens(_normalize_text(text)):
        token = _DETAIL_ALIASES.get(token, token)
        if token in META_WORDS or token in _DETAIL_STOPWORDS:
            continue
        tokens.add(token)
    return tokens


def _diagnosis_hay(entities: dict, indices: list[int]) -> set[str]:
    """Clinical words of the given diagnosis lines and their evidence quotes."""
    diagnoses = entities.get("diagnoses") or []
    parts = []
    for i in indices:
        if 0 <= i < len(diagnoses):
            parts.append(diagnoses[i].get("text") or "")
            evidence = diagnoses[i].get("evidence_text") or ""
            if evidence.strip().lower() != _NO_EVIDENCE_TEXT:
                parts.append(evidence)
    return _detail_tokens(" ".join(parts), strip_modifiers=False)


def _documented_detail(candidate: dict, selected: list[dict], hay: set[str]) -> tuple[float, list[str]]:
    """
    (support, undocumented words) for the detail a candidate ADDS to codes
    already chosen.

    E11.331 next to E11.9 adds "moderate nonproliferative retinopathy macular
    edema"; a note that never says any of it gives support 0.0. The old score
    credited E11.331 for "diabetes" and "mellitus" — words every E11 code
    shares — and that credit is what carried it over the 0.40 bar. A
    candidate that adds nothing (E13.42 beside E11.42, J18.8 beside J18.9) is
    another way to code a diagnosis already coded: support 0.0.
    """
    known: set[str] = set()
    for code in selected:
        known |= _detail_tokens(code.get("description", ""))
    added = _detail_tokens(candidate.get("description", "")) - known
    if not added:
        return 0.0, []
    missing = sorted(added - hay)
    return (len(added) - len(missing)) / len(added), missing


def _merge_candidates(existing: list[dict], additional: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for c in existing:
        code = c.get("code")
        if code:
            merged[code] = c
    for c in additional:
        code = c.get("code")
        if not code:
            continue
        if code not in merged:
            merged[code] = c
            continue
        # The same code found for two diagnoses codes both of them.
        union = sorted(set(merged[code].get("covers") or []) | set(c.get("covers") or []))
        existing_conf = float(merged[code].get("confidence") or 0.0)
        new_conf = float(c.get("confidence") or 0.0)
        if new_conf > existing_conf or c.get("source") == CONVENTION_SOURCE:
            merged[code] = {**merged[code], **c}
        if union:
            merged[code] = {**merged[code], "covers": union}
    return list(merged.values())


def _uses_icd11(state: CodingState, candidates: list[dict]) -> bool:
    mapping_path = str(state.get("mapping_path") or "")
    return mapping_path.startswith("who_api_icd11") or any(
        c.get("icd_version") == "ICD-11" for c in candidates
    )


def _same_code_system(candidate: dict, icd11: bool) -> bool:
    return (candidate.get("icd_version") == "ICD-11") == icd11


# ── ICD-10-CM "with" convention: diabetes + chronic kidney disease ──────────
# Guideline I.A.15: "with" in the Alphabetic Index presumes a causal link.
# The index entry "Diabetes, type 2, with, chronic kidney disease" is E11.22,
# and E11.22 carries "Use additional code to identify stage of CKD
# (N18.1-N18.6)". So a note documenting type 2 diabetes AND CKD stage 3 is
# E11.22 + N18.30 — even when the clinician never writes "diabetic CKD" —
# unless the documentation says the two are unrelated. No crosswalk, search
# or score produced that, because each looks at one phrase at a time.

_DIABETES_RE = re.compile(
    r"\bdiabet(?:es|ic)\b|\bt[12]dm\b|\bn?iddm\b|\bdm\s*(?:type\s*)?[12]\b"
    r"|\btype\s*(?:1|2|i|ii|one|two)\s+dm\b"
)
# Diabetes that is not E10/E11: E08, E09, E13, pregnancy (O24), insipidus.
# Each needs codes this rule cannot produce, so the rule stands aside.
_DIABETES_EXCLUDED_RE = re.compile(
    r"insipidus|pre[- ]?diabet|gestational|pregnan|puerper|childbirth|neonatal"
    r"|(?:drug|chemical|steroid)[- ]induced|due to (?:an )?underlying"
    r"|secondary diabet|other specified diabet"
)
_TYPE1_RE = re.compile(r"\btype\s*(?:1|i|one)\b|\bt1dm\b|\biddm\b|\bdm\s*(?:type\s*)?1\b")
_TYPE2_RE = re.compile(r"\btype\s*(?:2|ii|two)\b|\bt2dm\b|\bniddm\b|\bdm\s*(?:type\s*)?2\b")
_CKD_RE = re.compile(
    r"\bchronic kidney disease\b|\bckd\b|\bchronic renal (?:disease|failure|insufficiency)\b"
    r"|\bend[- ]stage (?:renal|kidney) disease\b|\besrd\b|\beskd\b"
)
_ESRD_RE = re.compile(r"\bend[- ]stage (?:renal|kidney) disease\b|\besrd\b|\beskd\b")
# A stage must be WRITTEN as a stage ("stage 3", "CKD 3b"). Nothing here
# reads eGFR or creatinine: coders may not assign a CKD stage from a lab
# value, only from the provider's documentation.
_CKD_STAGE_RE = re.compile(
    r"\b(?:stage|ckd)\s*(?:stage\s*)?(3a|3b|1|2|3|4|5|iii[ab]|iii|ii|iv|v|i)\b"
)
_DIALYSIS_RE = re.compile(r"\b(?:hemo|haemo)?dialysis\b")
_STAGE_CODES = {
    "1": "N18.1", "i": "N18.1",
    "2": "N18.2", "ii": "N18.2",
    "3": "N18.30", "iii": "N18.30",
    "3a": "N18.31", "iiia": "N18.31",
    "3b": "N18.32", "iiib": "N18.32",
    "4": "N18.4", "iv": "N18.4",
    "5": "N18.5", "v": "N18.5",
}
ESRD_CODE = "N18.6"
UNSTAGED_CKD_CODE = "N18.9"

_NEGATION_CUE_RE = re.compile(
    r"\b(?:no|not|without|denies|denied|negative for|ruled out|rule out|absence of|free of|never)\b|\br/o\b"
)
_SENTENCE_SPLIT_RE = re.compile(r"[.;:\n]+|\bbut\b|\bhowever\b")
# Denies kidney DISEASE. "No acute kidney injury" or "no renal artery
# stenosis" says nothing about a documented CKD.
_KIDNEY_DENIAL_RE = re.compile(
    r"\b(?:no|without|denies)\b[^.;:\n]*\b(?:kidney|renal) (?:disease|failure|insufficiency|impairment)\b"
    r"|\bnormal (?:kidney|renal) function\b|\b(?:kidney|renal) function (?:is )?normal\b"
)
_NO_COMPLICATIONS_RE = re.compile(
    r"\b(?:without|no)\s+(?:\w+\s+){0,2}complications?\b|\buncomplicated\b"
)
_UNRELATED_RE = re.compile(
    r"\b(?:not|un)\s*(?:due to|related to|caused by|secondary to)\s+(?:\w+\s+){0,2}diabet"
    r"|\bnon-?diabetic\b"
)


def _sentences(text: str) -> list[str]:
    return [s for s in _SENTENCE_SPLIT_RE.split((text or "").lower()) if s.strip()]


def _mentions(text: str, pattern: re.Pattern) -> tuple[bool, bool]:
    """
    (affirmed, negated) mentions of `pattern` in `text`.

    A mention is negated when a negation cue precedes it in the same sentence.
    Sentence scope is deliberately wide: "no retinopathy, neuropathy or CKD"
    must read as negated, and the cost of the rare wrong call is a code left
    for a human rather than a code billed on a denied condition.
    """
    affirmed = negated = False
    for sentence in _sentences(text):
        for match in pattern.finditer(sentence):
            if _NEGATION_CUE_RE.search(sentence[:match.start()]):
                negated = True
            else:
                affirmed = True
    return affirmed, negated


def _stages_in(text: str) -> set[str]:
    """CKD codes named in a piece of text: N18.6 wins over any written stage."""
    found: set[str] = set()
    for sentence in _sentences(text):
        if _ESRD_RE.search(sentence):
            found.add(ESRD_CODE)
            continue
        for match in _CKD_STAGE_RE.finditer(sentence):
            code = _STAGE_CODES[match.group(1)]
            if code == "N18.5" and _DIALYSIS_RE.search(sentence):
                code = ESRD_CODE   # stage 5 requiring dialysis is coded as ESRD
            found.add(code)
    if ESRD_CODE in found:
        return {ESRD_CODE}   # guideline I.C.14.a.2: stage and ESRD → N18.6 only
    return found


def _diabetes_ckd_plan(entities: dict, raw_text: str) -> tuple[dict | None, str]:
    """
    Decide whether the diabetes + CKD convention applies, from text alone.

    Returns (plan, reason). The plan names the combination code, the CKD
    stage code and which diagnosis lines they code; reason says why the rule
    did or did not fire, for the decision trace.
    """
    diagnoses = entities.get("diagnoses") or []
    texts = [(d.get("text") or "").lower() for d in diagnoses]
    raw = (raw_text or "").lower()

    ckd_lines, dm_lines = [], []
    for i, text in enumerate(texts):
        if _NEGATED_DIAGNOSIS_RE.search(text):
            continue
        if _mentions(text, _CKD_RE)[0]:
            ckd_lines.append(i)
        if _mentions(text, _DIABETES_RE)[0]:
            dm_lines.append(i)
    if not ckd_lines or not dm_lines:
        return None, "not_documented"

    dm_text = " ".join(texts[i] for i in dm_lines)
    everything = " ".join(texts) + " " + raw
    if _DIABETES_EXCLUDED_RE.search(dm_text):
        return None, "diabetes_type_not_supported"
    if _mentions(raw, _CKD_RE)[1] or _KIDNEY_DENIAL_RE.search(everything):
        return None, "kidney_disease_denied"
    if _NO_COMPLICATIONS_RE.search(everything):
        return None, "documentation_conflict"
    if _UNRELATED_RE.search(everything):
        return None, "documented_as_unrelated"

    types = set()
    if _TYPE1_RE.search(dm_text):
        types.add("E10")
    if _TYPE2_RE.search(dm_text):
        types.add("E11")
    if not types:
        for sentence in _sentences(raw):
            if _DIABETES_RE.search(sentence):
                if _TYPE1_RE.search(sentence):
                    types.add("E10")
                if _TYPE2_RE.search(sentence):
                    types.add("E11")
    if len(types) > 1:
        return None, "diabetes_type_conflict"
    # Guideline I.C.4.a.2: type not documented → type 2.
    category = types.pop() if types else "E11"

    stages: set[str] = set()
    for i in ckd_lines:
        stages |= _stages_in(texts[i])
    stage_source = "diagnosis"
    if not stages:
        stage_source = "note"
        for sentence in _sentences(raw):
            if _mentions(sentence, _CKD_RE)[0]:
                stages |= _stages_in(sentence)
    if len(stages) == 1:
        stage_code = stages.pop()
    else:
        stage_code = UNSTAGED_CKD_CODE
        stage_source = "conflicting" if stages else "not_documented"

    return {
        "combination_code": f"{category}.22",
        "stage_code":       stage_code,
        "stage_source":     stage_source,
        "ckd_lines":        ckd_lines,
        "diabetes_lines":   dm_lines,
    }, "applied"


async def _diabetes_ckd_candidates(entities: dict, raw_text: str) -> tuple[list[dict], dict]:
    """
    Candidates for the diabetes + CKD convention, and a trace entry.

    Raises when the codes the rule requires are missing from icd_codes:
    without them the pipeline would fall back to "without complications",
    which the documentation contradicts. Failing the run sends it to a human.
    """
    plan, reason = _diabetes_ckd_plan(entities, raw_text)
    if plan is None:
        return [], {"rule": "diabetes_ckd", "applied": False, "reason": reason}

    combo_code, stage_code = plan["combination_code"], plan["stage_code"]
    rows = await select(
        table="icd_codes",
        query="code,description,is_billable,is_cc,is_mcc,base_reimbursement,version",
        filters={"code": f"in.({combo_code},{stage_code})"},
    )
    by_code = {r.get("code"): r for r in rows or []}
    for code in (combo_code, stage_code):
        if not by_code.get(code) or not by_code[code].get("is_billable"):
            raise ValueError(f"ICD-10-CM convention code {code} is missing or not billable in icd_codes")

    def _candidate(row: dict, mapping_type: str, covers: list[int]) -> dict:
        return {
            "code":               row["code"],
            "description":        row["description"],
            "is_billable":        True,
            "is_cc":              bool(row.get("is_cc")),
            "is_mcc":             bool(row.get("is_mcc")),
            "base_reimbursement": float(row.get("base_reimbursement") or 0),
            "icd_version":        row.get("version") or "ICD-10-CM-2024",
            "mapping_type":       mapping_type,
            "confidence":         1.0,
            "is_primary":         False,
            "source":             CONVENTION_SOURCE,
            "covers":             covers,
        }

    combo_row = by_code[combo_code]
    # The combination code also codes a diabetes line that says nothing
    # beyond "type 2 diabetes mellitus". A line naming another complication
    # ("... with diabetic polyneuropathy") still needs its own code.
    combo_words = _detail_tokens(combo_row["description"])
    diagnoses = entities.get("diagnoses") or []
    plain_dm_lines = [
        i for i in plan["diabetes_lines"]
        if _detail_tokens(diagnoses[i].get("text") or "", strip_modifiers=False)
        - _DIABETES_SHORTHAND <= combo_words
    ]
    combo_covers = sorted(set(plan["ckd_lines"]) | set(plain_dm_lines))

    combo = _candidate(combo_row, "guideline_with", combo_covers)
    stage = _candidate(by_code[stage_code], "guideline_use_additional", list(plan["ckd_lines"]))
    stage["use_additional_for"] = combo_code
    trace = {
        "rule":         "diabetes_ckd",
        "applied":      True,
        "codes":        [combo_code, stage_code],
        "stage_source": plan["stage_source"],
        "covers":       combo_covers,
    }
    return [combo, stage], trace


def _claims_no_complications(candidate: dict) -> bool:
    return "without complications" in (candidate.get("description") or "").lower()


# ── Resolving every diagnosis ───────────────────────────────────────────────

async def _resolve_remaining_diagnoses(
    entities: dict, candidates: list[dict], org_id: str | None, icd11: bool, session_id: str,
) -> tuple[list[dict], bool, dict[int, str]]:
    """
    Look up candidates for each diagnosis after the first that no candidate
    covers yet. Returns (new candidates, provider_used, status per line).

    Text search runs first; vector search (ICD-10-CM only) runs when no text
    result is fully documented by that line.
    """
    diagnoses = entities.get("diagnoses") or []
    covered = {i for c in candidates for i in _covers(c)}
    seen: set[str] = set()
    found: list[dict] = []
    statuses: dict[int, str] = {}
    provider_used = False
    lookups = 0

    for i, diagnosis in enumerate(diagnoses):
        text = (diagnosis.get("text") or "").strip()
        key = text.lower()
        if i == 0 or i in covered:
            seen.add(key)
            continue
        if key in seen:
            statuses[i] = "duplicate"   # coded by its first occurrence
            continue
        seen.add(key)
        if not text:
            statuses[i] = "empty"
            continue
        if _NEGATED_DIAGNOSIS_RE.search(key):
            statuses[i] = "negated"
            continue
        if lookups >= MAX_DIAGNOSES_LOOKED_UP:
            statuses[i] = "not_looked_up"
            continue
        lookups += 1

        results: list[dict] = []
        try:
            results = await _provider_candidates(entities, org_id, [i])
        except Exception as exc:
            log.warning("icd_diagnosis_lookup_failed", session_id=session_id,
                        diagnosis_index=i, error_type=type(exc).__name__, error=str(exc))
        results = [r for r in results if _same_code_system(r, icd11)]
        provider_used = provider_used or bool(results)

        hay = _diagnosis_hay(entities, [i])
        if not icd11 and not any(_detail_tokens(r.get("description", "")) <= hay for r in results):
            vector = await find_icd_candidates_by_vector(text, session_id)
            results = results + [_with_covers(v, [i]) for v in vector]

        statuses[i] = "looked_up" if results else "no_candidates"
        found = _merge_candidates(found, results)

    return found, provider_used, statuses


# ── Choosing the codes ──────────────────────────────────────────────────────

def _select_codes(scored: list[dict], entities: dict) -> tuple[list[tuple[dict, str, str]], dict]:
    """
    Pick the claim's codes from scored candidates (sorted best first).

    Returns ([(candidate, role, reason)], trace). Rules, in order:
      1. Primary: the best candidate coding diagnoses[0]. A convention
         combination code for that line wins unless a same-category code
         whose extra detail is fully documented outscores it.
      2. A convention combination code is always coded; its "use additional
         code" partner (the CKD stage) follows it.
      3. Each other diagnosis gets its best candidate scoring >= 0.40 whose
         added detail the line documents (MIN_DOCUMENTED_DETAIL).
      4. A further code for an already-coded line is kept only when it is in
         the same category and its added detail is documented the same way —
         one note can have several diabetic complications, but "portal
         hypertension" is not a second code for a line that says
         "hypertension".
    """
    diagnoses = entities.get("diagnoses") or []
    line_count = max(len(diagnoses), 1)
    eligible = [c for c in scored if not c.get("use_additional_for")]
    chosen: list[tuple[dict, str, str]] = []
    chosen_codes: set[str] = set()
    coded_lines: dict[int, list[str]] = {}

    def selected() -> list[dict]:
        return [c for c, _, _ in chosen]

    def add(candidate: dict, role: str, reason: str) -> None:
        if candidate["code"] in chosen_codes or len(chosen) >= MAX_ICD_CODES:
            return
        chosen.append((candidate, role, reason))
        chosen_codes.add(candidate["code"])
        for i in _covers(candidate):
            coded_lines.setdefault(i, []).append(candidate["code"])
        for partner in scored:
            if partner.get("use_additional_for") == candidate["code"]:
                add(partner, "additional", "identifies the CKD stage")

    # 1. Primary
    first_line = [c for c in eligible if 0 in _covers(c)]
    combo = next((c for c in first_line if c.get("source") == CONVENTION_SOURCE), None)
    primary_note = ""
    if combo is not None:
        hay0 = _diagnosis_hay(entities, [0])
        contenders = [combo] + [
            c for c in first_line
            if c is not combo and c["code"][:3] == combo["code"][:3]
            and _documented_detail(c, [combo], hay0)[0] == 1.0
        ]
        primary = max(contenders, key=lambda c: c["final_score"])
    elif first_line:
        primary = first_line[0]
    else:
        primary = eligible[0] if eligible else scored[0]
        primary_note = "first diagnosis could not be coded"
    add(primary, "primary", primary_note)

    rejected: list[dict] = []
    for i in range(line_count):
        # 2. Mandated combination codes
        for c in eligible:
            if c.get("source") == CONVENTION_SOURCE and i in _covers(c):
                add(c, "secondary", "ICD-10-CM 'with' convention: diabetes and CKD are presumed linked")
        hay = _diagnosis_hay(entities, [i])

        # 3. A code for a line nothing has coded yet
        if i not in coded_lines:
            for c in eligible:
                if i not in _covers(c) or c["code"] in chosen_codes:
                    continue
                support, missing = _documented_detail(c, selected(), hay)
                if c["final_score"] >= SECONDARY_MIN_SCORE and support >= MIN_DOCUMENTED_DETAIL:
                    add(c, "secondary", f"codes documented diagnosis #{i + 1}")
                    break
                rejected.append({"code": c["code"], "line": i, "reason": "undocumented_detail"
                                 if c["final_score"] >= SECONDARY_MIN_SCORE else "below_threshold",
                                 "missing": missing[:5]})

        # 4. Further documented detail for a coded line
        line_categories = {code[:3] for code in coded_lines.get(i, [])}
        for c in eligible:
            if i not in _covers(c) or c["code"] in chosen_codes:
                continue
            support, missing = _documented_detail(c, selected(), hay)
            if (c["code"][:3] in line_categories and support >= MIN_DOCUMENTED_DETAIL
                    and c["final_score"] >= SECONDARY_MIN_SCORE):
                add(c, "additional", f"additional documented detail for diagnosis #{i + 1}")
            elif i in coded_lines and not any(r["code"] == c["code"] for r in rejected):
                rejected.append({"code": c["code"], "line": i,
                                 "reason": "undocumented_detail" if missing else "alternative_code",
                                 "missing": missing[:5]})

    rejected = [r for r in rejected if r["code"] not in chosen_codes]
    trace = {
        "lines": [
            {"index": i, "codes": coded_lines.get(i, [])} for i in range(len(diagnoses))
        ],
        "rejected": rejected[:10],
    }
    return chosen, trace


@safe_node("icd_decision")
async def icd_decision_node(state: CodingState) -> CodingState:
    """
    LangGraph Node 6 — Deterministic ICD Decision.
    Input:  state["candidate_icd_codes"], state["structured_entities"]
    Output: state["final_icd_code"], state["confidence_score"], state["icd_codes"]

    Upstream nodes only code diagnoses[0]. This node also applies the
    diabetes + CKD "with" convention (ICD-10-CM only), looks up the other
    diagnoses, and then chooses codes per diagnosis (see _select_codes).
    Scoring weights are unchanged.
    """
    session_id = str(state.get("session_id", ""))
    entities   = state.get("structured_entities") or {}
    raw_text   = state.get("raw_text", "")   # for negation detection
    org_id     = state.get("org_id")
    provider_used = False
    # Everything upstream describes the first diagnosis.
    candidates = [_with_covers(c, [0]) for c in (state.get("candidate_icd_codes") or [])]

    # ── Provider augmentation (if candidates are missing or thin) ──────────
    if (not candidates) or len(candidates) < 3:
        provider_candidates = await _provider_candidates(entities, org_id, [0])
        if provider_candidates:
            provider_used = True
            candidates = _merge_candidates(candidates, provider_candidates)
            if not state.get("mapping_path"):
                state["mapping_path"] = "provider_fallback"
            elif state.get("mapping_path") not in {"provider_fallback", "provider_augmented"}:
                state["mapping_path"] = "provider_augmented"

    # ── ICD-10-CM "with" convention (never on the ICD-11 path) ─────────────
    icd11 = _uses_icd11(state, candidates)
    suppressed: list[str] = []
    if icd11:
        convention_trace = {"rule": "diabetes_ckd", "applied": False, "reason": "icd11_path"}
    else:
        convention, convention_trace = await _diabetes_ckd_candidates(entities, raw_text)
        if convention:
            # A documented diabetic complication contradicts every
            # "without complications" code, however well it scored.
            suppressed = [c["code"] for c in candidates if _claims_no_complications(c)]
            candidates = [c for c in candidates if not _claims_no_complications(c)]
            candidates = _merge_candidates(candidates, convention)
            log.info("icd_convention_applied", session_id=session_id,
                     codes=convention_trace["codes"], stage_source=convention_trace["stage_source"],
                     suppressed=suppressed)

    # ── Every other diagnosis ───────────────────────────────────────────────
    found, found_via_provider, line_status = await _resolve_remaining_diagnoses(
        entities, candidates, org_id, icd11, session_id,
    )
    provider_used = provider_used or found_via_provider
    candidates = _merge_candidates(candidates, found)

    extra_trace = {
        "convention": convention_trace,
        "suppressed_codes": suppressed,
        "line_status": {str(i): s for i, s in line_status.items()},
    }

    # ── Guard: no candidates ────────────────────────────────────────────────
    if not candidates:
        log.warning("icd_decision_no_candidates", session_id=session_id,
                    mapping_path=state.get("mapping_path"))
        state["final_icd_code"]   = "UNKNOWN"
        state["confidence_score"] = 0.0
        state["icd_codes"]        = []
        state["decision_trace"]   = _decision_trace(state, [], provider_used, extra_trace)
        return state

    candidates = [c for c in candidates if c.get("is_billable", True)]
    if not candidates:
        state["final_icd_code"]   = "UNKNOWN"
        state["confidence_score"] = 0.0
        state["icd_codes"]        = []
        state["decision_trace"]   = _decision_trace(state, [], provider_used, extra_trace)
        return state

    # ── Score every candidate FIRST ─────────────────────────────────────────
    # NOTE: _apply_gold_standard_keywords and _penalize_unspecified_codes both
    # read candidate["final_score"], so they MUST run after this loop.
    scored = []
    for c in candidates:
        score = _final_score(c, entities, raw_text)
        scored.append({**c, "final_score": score})

    # ── Apply Gold Standard Keyword Matching (requires final_score set) ──────
    scored = _apply_gold_standard_keywords(scored, raw_text)

    # ── Penalize Unspecified Codes (requires final_score set) ────────────────
    scored = _penalize_unspecified_codes(scored, raw_text)

    scored.sort(key=lambda x: x["final_score"], reverse=True)

    # ── Choose codes per diagnosis (RCM-style multi-code list) ──────────────
    chosen, selection_trace = _select_codes(scored, entities)
    winner = chosen[0][0]

    state["final_icd_code"]      = winner["code"]
    state["confidence_score"]    = winner["final_score"]
    state["candidate_icd_codes"] = scored

    icd_codes = [
        {
            "code":               c["code"],
            "description":        c.get("description", ""),
            "role":               role,
            "final_score":        c["final_score"],
            "is_mcc":             c.get("is_mcc", False),
            "is_cc":              c.get("is_cc", False),
            "base_reimbursement": c.get("base_reimbursement", 0),
            "rationale":          _rationale(c, reason),
        }
        for c, role, reason in chosen
    ]

    state["icd_codes"] = icd_codes
    state["decision_trace"] = _decision_trace(
        state, scored, provider_used, {**extra_trace, **selection_trace},
    )

    log.info(
        "icd_selected",
        session_id=session_id,
        final_icd_code=winner["code"],
        confidence_score=winner["final_score"],
        mapping_path=state.get("mapping_path"),
        candidates_evaluated=len(scored),
        multi_codes_returned=len(icd_codes),
        codes=[c["code"] for c in icd_codes],
        runner_up=next((c["code"] for c in scored if c["code"] != winner["code"]), None),
        rejected=len(selection_trace["rejected"]),
    )
    return state


def _rationale(c: dict, reason: str = "") -> str:
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
    elif mt == "guideline_with":
        parts.append("ICD-10-CM 'with' convention (guideline I.A.15)")
    elif mt == "guideline_use_additional":
        parts.append("required by the combination code's 'use additional code' note")
    if reason and reason not in parts:
        parts.append(reason)
    if not parts:
        parts.append("billable ICD-10-CM code")
    return "; ".join(parts)


async def _provider_candidates(
    entities: dict, org_id: str | None, indices: list[int] | None = None,
) -> list[dict]:
    """
    Text-search candidates for the given diagnosis lines (default: the first),
    each tagged with the line it was found for.
    """
    if not org_id:
        return []

    diagnoses = entities.get("diagnoses", [])
    candidates: list[dict] = []
    searched: set[str] = set()
    for i in (indices if indices is not None else [0]):
        if not (0 <= i < len(diagnoses)):
            continue
        text = (diagnoses[i].get("text") or "").strip()
        if not text or text.lower() in searched:
            continue
        searched.add(text.lower())

        for r in await get_icd_results(text, org_id, limit=5):
            candidates.append(
                {
                    "code":               r.get("code"),
                    "description":        r.get("description"),
                    "is_billable":        r.get("is_billable", True),
                    "is_cc":              r.get("is_cc", False),
                    "is_mcc":             r.get("is_mcc", False),
                    "base_reimbursement": r.get("base_reimbursement") or 0.0,
                    "icd_version":        "ICD-11" if r.get("source") == "ICD-11" else "ICD-10",
                    "mapping_type":       "provider",
                    "confidence":         float(r.get("score") or 0.0),
                    "is_primary":         False,
                    "source":             "icd_provider",
                    "similarity_score":   float(r.get("score") or 0.0),
                    "covers":             [i],
                }
            )
    return _merge_candidates([], candidates)


def _decision_trace(
    state: CodingState, candidates: list[dict], provider_used: bool, extra: dict | None = None,
) -> dict:
    mapping_path = state.get("mapping_path")
    used_snomed = bool(state.get("resolved_snomed_code")) or mapping_path in {"direct", "embedding"}
    used_icd11 = any((c.get("icd_version") == "ICD-11") for c in candidates) or (
        isinstance(mapping_path, str) and mapping_path.startswith("who_api")
    )
    used_icd10 = any(("ICD-10" in str(c.get("icd_version"))) for c in candidates)
    return {
        "used_snomed": used_snomed,
        "used_icd10": used_icd10,
        "used_icd11": used_icd11,
        "fallback_used": provider_used,
        "coding_mode": state.get("coding_mode"),
        **(extra or {}),
    }

def _finalize_decision(state):
    try:
        candidates = state.get("candidate_icd_codes", [])  # Ensure candidates is defined
        if not candidates:
            raise ValueError("No candidates available for decision.")

        best_candidate = max(candidates, key=lambda c: c.get("final_score", 0))  # Ensure best_candidate is defined
        state["final_score"] = best_candidate.get("final_score", 0.0)
        state["final_icd_code"] = best_candidate.get("code", "UNKNOWN")
        state["confidence_score"] = best_candidate.get("confidence", 0.0)
    except Exception as e:
        log.error("Error in icd_decision node: %s", str(e))
        state["final_score"] = 0.0  # Default value
        state["final_icd_code"] = "UNKNOWN"
        state["confidence_score"] = 0.0
