"""
This agent takes the clinical entities extracted by the LLM and tries to
find a matching, standardized SNOMED CT concept code for the primary diagnosis.
It uses a couple of strategies, from direct lookups to intelligent text searching,
to find the most accurate SNOMED code.
"""
from agents.graph import CodingState
from agents.node_runner import safe_node
from database import select_one, select
from logger import get_logger

log = get_logger(__name__)


@safe_node("snomed_resolve")
async def snomed_resolver_node(state: CodingState) -> CodingState:
    # This is the third node in our graph. Its job is to find a standard
    # SNOMED code for the diagnosis that the LLM extracted.
    session_id = str(state.get("session_id", ""))
    entities = state.get("structured_entities", {})
    diagnoses = entities.get("diagnoses", [])

    if not diagnoses:
        # If there's no diagnosis, we can't find a code.
        state["resolved_snomed_code"] = None
        state["snomed_resolution_method"] = "not_found"
        return state

    # The LLM often suggests a SNOMED code, so we'll try that first.
    candidate = diagnoses[0].get("snomed_candidate", {})
    suggested_code = candidate.get("code")

    # Strategy 1: Look up the LLM's suggested code directly in our database.
    if suggested_code:
        row = await select_one(
            table="snomed_concepts",
            query="snomed_code,description",
            filters={"snomed_code": f"eq.{suggested_code}", "is_active": "eq.true"},
        )
        if row:
            # If we find a valid, active code, we're done!
            state["resolved_snomed_code"] = row["snomed_code"]
            state["resolved_snomed_desc"] = row["description"]
            state["snomed_resolution_method"] = "llm_suggested"
            log.info("snomed_resolved", session_id=session_id,
                     method="llm_suggested", code=row["snomed_code"])
            return state

    # Strategy 2: If the direct lookup fails, we'll try searching by the diagnosis text.
    diagnosis_text = diagnoses[0].get("text", "").strip()
    if not diagnosis_text:
        state["resolved_snomed_code"] = None
        state["snomed_resolution_method"] = "not_found"
        return state

    # We'll clean up the text by removing common, meaningless words.
    stop_words = {"patient", "has", "with", "the", "and", "or", "a", "an",
                  "is", "was", "of", "for", "no", "not", "without", "history",
                  "also", "both", "been", "well", "type", "stage"}
    meaningful_words = [
        w.strip(".,;") for w in diagnosis_text.lower().split()
        if w.strip(".,;") not in stop_words and len(w.strip(".,;")) > 3
    ]

    # We create search phrases, starting with the most specific (two-word pairs)
    # and falling back to the single longest word.
    two_word_pairs = [
        f"{meaningful_words[i]} {meaningful_words[i+1]}"
        for i in range(len(meaningful_words) - 1)
    ] if len(meaningful_words) >= 2 else []

    single_longest = [max(meaningful_words, key=len)] if meaningful_words else []

    search_phrases = two_word_pairs + single_longest

    # Now we search our SNOMED database with these phrases.
    resolved = None
    for phrase in search_phrases:
        rows = await select(
            table="snomed_concepts",
            query="snomed_code,description",
            filters={
                "description": f"ilike.*{phrase}*",
                "is_active":   "eq.true",
            },
            limit=1,   # FIX: limit is now a proper param, not embedded in filters
        )
        if rows:
            resolved = rows[0]
            break  # Take the first match we find.


    if resolved:
        state["resolved_snomed_code"] = resolved["snomed_code"]
        state["resolved_snomed_desc"] = resolved["description"]
        state["snomed_resolution_method"] = "text_matched"
        log.info("snomed_resolved", session_id=session_id,
                 method="text_matched", code=resolved["snomed_code"])
        return state

    # If we still can't find anything, we mark it as not found.
    # The next steps in the graph will handle this case.
    state["resolved_snomed_code"] = None
    state["snomed_resolution_method"] = "not_found"
    log.warning("snomed_not_resolved", session_id=session_id, diagnosis=diagnosis_text[:60])
    return state

