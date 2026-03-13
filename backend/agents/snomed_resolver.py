"""
agents/snomed_resolver.py — ICD Code Resolver (WHO ICD API + SNOMED fallback)

Upgrade (Phase 1 — WHO ICD API integration):
  Primary path:  WHO ICD API search → returns ICD codes directly
  Fallback path: Original SNOMED concept lookup (when WHO API unavailable/returns 0)

The WHO ICD API replaces the old SNOMED→crosswalk→embedding chain for the
primary diagnosis. It queries WHO's authoritative live classification and returns
ranked ICD candidate codes in a single HTTP call.

ICD version used is read from pipeline state:
  - "ICD-11" (default) → Ayushman Bharat / ABDM aligned, India mandate
  - "ICD-10"           → legacy private insurer systems (org_settings override)
"""
from agents.graph import CodingState
from agents.node_runner import safe_node
from services.who_icd_service import search_icd, enrich_with_local_flags
from database import select_one, select
from logger import get_logger

log = get_logger(__name__)


@safe_node("snomed_resolve")
async def snomed_resolver_node(state: CodingState) -> CodingState:
    session_id   = str(state.get("session_id", ""))
    entities     = state.get("structured_entities", {})
    diagnoses    = entities.get("diagnoses", [])
    icd_version  = state.get("icd_version", "ICD-11")   # set by code router from org_settings

    if not diagnoses:
        state["resolved_snomed_code"]      = None
        state["snomed_resolution_method"]  = "not_found"
        state["who_icd_candidates"]        = []
        return state

    primary_diagnosis = diagnoses[0]
    diagnosis_text    = primary_diagnosis.get("text", "").strip()

    # ── PATH 1: WHO ICD API (primary — authoritative, always current) ─────────
    log.info(
        "who_icd_search_start",
        session_id=session_id,
        query=diagnosis_text[:80],
        version=icd_version,
    )

    who_results = await search_icd(
        query=diagnosis_text,
        icd_version=icd_version,
        limit=10,
    )

    if who_results:
        # Enrich with CC/MCC flags + base_reimbursement from local cache
        who_results = await enrich_with_local_flags(who_results)

        # Store all WHO candidates in state for Node 6 (decision engine)
        state["who_icd_candidates"]       = who_results
        state["mapping_path"]             = f"who_api_{icd_version.lower().replace('-', '')}"
        state["resolved_snomed_code"]     = None          # Not needed — WHO skips SNOMED
        state["resolved_snomed_desc"]     = None
        state["snomed_resolution_method"] = f"who_api_{icd_version}"

        # Pre-populate candidate_icd_codes in the format Node 4/5 would have produced
        # This lets Node 6 (icd_decision_engine) work unchanged
        state["candidate_icd_codes"] = [
            {
                "code":               r["code"],
                "description":        r["description"],
                "is_billable":        True,
                "is_cc":              r.get("is_cc", False),
                "is_mcc":             r.get("is_mcc", False),
                "base_reimbursement": r.get("base_reimbursement", 5000.0),
                "icd_version":        r["icd_version"],
                "mapping_type":       r["mapping_type"],
                "confidence":         r["score"],
                "is_primary":         True if r == who_results[0] else False,
                "source":             "who_icd_api",
                "similarity_score":   r["score"],
            }
            for r in who_results
        ]
        state["direct_mapped_icd"] = who_results[0]["code"]

        log.info(
            "who_icd_candidates_ready",
            session_id=session_id,
            top_code=who_results[0]["code"],
            top_title=who_results[0]["description"][:60],
            total=len(who_results),
            version=icd_version,
        )
        return state

    # ── PATH 2: SNOMED fallback (original logic — runs when WHO API returns 0) ─
    log.warning(
        "who_icd_empty_falling_back_to_snomed",
        session_id=session_id,
        query=diagnosis_text[:60],
    )
    state["who_icd_candidates"] = []

    # Try LLM-suggested SNOMED code first
    candidate     = primary_diagnosis.get("snomed_candidate", {})
    suggested_code = candidate.get("code")
    if suggested_code:
        row = await select_one(
            table="snomed_concepts",
            query="snomed_code,description",
            filters={"snomed_code": f"eq.{suggested_code}", "is_active": "eq.true"},
        )
        if row:
            state["resolved_snomed_code"]     = row["snomed_code"]
            state["resolved_snomed_desc"]     = row["description"]
            state["snomed_resolution_method"] = "llm_suggested_fallback"
            log.info("snomed_fallback_resolved", session_id=session_id, code=row["snomed_code"])
            return state

    # Text search fallback
    stop_words = {"patient", "has", "with", "the", "and", "or", "a", "an",
                  "is", "was", "of", "for", "no", "not", "without", "history",
                  "also", "both", "been", "well", "type", "stage"}
    meaningful_words = [
        w.strip(".,;") for w in diagnosis_text.lower().split()
        if w.strip(".,;") not in stop_words and len(w.strip(".,;")) > 3
    ]
    two_word_pairs = [
        f"{meaningful_words[i]} {meaningful_words[i+1]}"
        for i in range(len(meaningful_words) - 1)
    ] if len(meaningful_words) >= 2 else []
    single_longest = [max(meaningful_words, key=len)] if meaningful_words else []
    search_phrases = two_word_pairs + single_longest

    resolved = None
    for phrase in search_phrases:
        rows = await select(
            table="snomed_concepts",
            query="snomed_code,description",
            filters={"description": f"ilike.*{phrase}*", "is_active": "eq.true"},
            limit=1,
        )
        if rows:
            resolved = rows[0]
            break

    if resolved:
        state["resolved_snomed_code"]     = resolved["snomed_code"]
        state["resolved_snomed_desc"]     = resolved["description"]
        state["snomed_resolution_method"] = "text_matched_fallback"
        log.info("snomed_text_fallback_resolved", session_id=session_id, code=resolved["snomed_code"])
        return state

    # Nothing found anywhere
    state["resolved_snomed_code"]     = None
    state["snomed_resolution_method"] = "not_found"
    log.warning("snomed_not_resolved", session_id=session_id, diagnosis=diagnosis_text[:60])
    return state
