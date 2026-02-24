"""
agents/snomed_resolver.py — Node 3: SNOMED Concept Resolver
"""
from agents.graph import CodingState
from agents.node_runner import safe_node
from database import select_one, select
from logger import get_logger

log = get_logger(__name__)


@safe_node("snomed_resolve")
async def snomed_resolver_node(state: CodingState) -> CodingState:
    """
    LangGraph Node 3 — SNOMED Concept Resolution.
    Input:  state["structured_entities"]["diagnoses"][0]["snomed_candidate"]
    Output: state["resolved_snomed_code"], state["snomed_resolution_method"]
    """
    session_id = str(state.get("session_id", ""))
    entities = state.get("structured_entities", {})
    diagnoses = entities.get("diagnoses", [])

    if not diagnoses:
        state["resolved_snomed_code"] = None
        state["snomed_resolution_method"] = "not_found"
        return state

    candidate = diagnoses[0].get("snomed_candidate", {})
    suggested_code = candidate.get("code")

    # Strategy 1: Direct lookup by LLM-suggested SNOMED code
    if suggested_code:
        row = await select_one(
            table="snomed_concepts",
            query="snomed_code,description",
            filters={"snomed_code": f"eq.{suggested_code}", "is_active": "eq.true"},
        )
        if row:
            state["resolved_snomed_code"] = row["snomed_code"]
            state["resolved_snomed_desc"] = row["description"]
            state["snomed_resolution_method"] = "llm_suggested"
            log.info("snomed_resolved", session_id=session_id,
                     method="llm_suggested", code=row["snomed_code"])
            return state

    # Strategy 2: Full-phrase text search (improved — not just first word)
    diagnosis_text = diagnoses[0].get("text", "").strip()
    if not diagnosis_text:
        state["resolved_snomed_code"] = None
        state["snomed_resolution_method"] = "not_found"
        return state

    # Build ranked search strategies — order: most specific first
    stop_words = {"patient", "has", "with", "the", "and", "or", "a", "an",
                  "is", "was", "of", "for", "no", "not", "without", "history",
                  "also", "both", "been", "well", "type", "stage"}
    meaningful_words = [
        w.strip(".,;") for w in diagnosis_text.lower().split()
        if w.strip(".,;") not in stop_words and len(w.strip(".,;")) > 3
    ]

    # Strategy A: 2-word sliding window pairs (most effective)
    # "chronic low back pain" → tries "chronic low", "low back", "back pain"
    # "back pain" → matches DB "Low back pain" ✅
    two_word_pairs = [
        f"{meaningful_words[i]} {meaningful_words[i+1]}"
        for i in range(len(meaningful_words) - 1)
    ] if len(meaningful_words) >= 2 else []

    # Strategy B: Single longest word as last resort
    single_longest = [max(meaningful_words, key=len)] if meaningful_words else []

    search_phrases = two_word_pairs + single_longest

    resolved = None
    for phrase in search_phrases:
        rows = await select(
            table="snomed_concepts",
            query="snomed_code,description",
            filters={
                "description": f"ilike.*{phrase}*",
                "is_active":   "eq.true",
                "limit":       "1",
            },
        )
        if rows:
            resolved = rows[0]
            break

    if resolved:
        state["resolved_snomed_code"] = resolved["snomed_code"]
        state["resolved_snomed_desc"] = resolved["description"]
        state["snomed_resolution_method"] = "text_matched"
        log.info("snomed_resolved", session_id=session_id,
                 method="text_matched", code=resolved["snomed_code"])
        return state

    # Fallback: not found — Node 5 embedding will handle it
    state["resolved_snomed_code"] = None
    state["snomed_resolution_method"] = "not_found"
    log.warning("snomed_not_resolved", session_id=session_id, diagnosis=diagnosis_text[:60])
    return state

