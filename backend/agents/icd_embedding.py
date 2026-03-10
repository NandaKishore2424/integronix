"""
This agent is our fallback plan. It's triggered only when a direct, official
mapping from SNOMED to ICD-10 can't be found. It uses vector embeddings to
find ICD-10 codes that are semantically similar to the clinical text.
This ensures we can always suggest a code, even for complex cases.
"""
from __future__ import annotations
from agents.graph import CodingState
from agents.node_runner import safe_node
from database import rpc
from logger import get_logger

log = get_logger(__name__)

SIMILARITY_THRESHOLD = 0.55   # We need a minimum similarity to consider a match.
EMBEDDING_TOP_K = 5           # We'll only consider the top 5 most similar codes.

# This map helps us avoid suggesting codes from completely unrelated medical specialties.
# For example, if the diagnosis is about diabetes, we shouldn't suggest a code for a mental disorder.
UNRELATED_CHAPTER_PAIRS = {
    "Endocrine":     {"Mental", "Neuro"},
    "Mental":        {"Endocrine", "Infectious"},
    "Circulatory":   {"Mental", "MSK"},
    "Respiratory":   {"Mental", "Digestive", "MSK"},
    "Infectious":    {},
}

_embedding_model = None


def _get_model():
    # We lazy-load the embedding model so it's only loaded into memory when needed.
    # The first time this is called, it will download the model (if necessary).
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
            log.info("embedding_model_loaded", model="all-MiniLM-L6-v2")
        except ImportError:
            log.error("embedding_model_missing",
                      error="sentence-transformers not installed. Run: pip install sentence-transformers")
            raise
    return _embedding_model


def _embed_text(text: str) -> list[float]:
    # This function takes a string of text and turns it into a 384-dimension vector.
    model = _get_model()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


def _vector_to_pg_literal(vector: list[float]) -> str:
    # A helper function to format the vector into the string format that
    # our PostgreSQL database (pgvector) expects.
    return "[" + ",".join(f"{v:.8f}" for v in vector) + "]"


def _infer_chapter_from_diagnoses(entities: dict) -> str | None:
    # A simple heuristic to guess the relevant medical chapter from the diagnosis text.
    # This helps us filter out irrelevant search results later.
    text = " ".join(
        d.get("text", "").lower() for d in entities.get("diagnoses", [])
    )
    if any(w in text for w in ["diabetes", "thyroid", "lipid", "endocrine"]):
        return "Endocrine"
    if any(w in text for w in ["heart", "cardiac", "hypertension", "atrial"]):
        return "Circulatory"
    if any(w in text for w in ["pneumonia", "asthma", "copd", "respiratory", "lung"]):
        return "Respiratory"
    if any(w in text for w in ["depression", "anxiety", "mental", "psychiatric"]):
        return "Mental"
    if any(w in text for w in ["back pain", "arthritis", "bone", "fracture"]):
        return "MSK"
    if any(w in text for w in ["diarrhea", "bowel", "gastro", "liver", "reflux"]):
        return "Digestive"
    if any(w in text for w in ["sepsis", "infection", "bacterial", "viral"]):
        return "Infectious"
    return None


@safe_node("icd_embedding")
async def icd_embedding_node(state: CodingState) -> CodingState:
    # This is the main function for the embedding node. It's only called
    # when the previous node couldn't find a direct mapping.
    session_id = str(state.get("session_id", ""))
    entities   = state.get("structured_entities") or {}
    diagnoses  = entities.get("diagnoses", [])

    if not diagnoses:
        log.warning("embedding_no_diagnoses", session_id=session_id)
        state["candidate_icd_codes"] = []
        state["mapping_path"] = "no_mapping"
        return state

    # Use the primary (first) diagnosis for embedding
    primary_text = diagnoses[0].get("text", "").strip()
    if not primary_text:
        state["candidate_icd_codes"] = []
        return state

    # Infer chapter context for exclusion guardrail
    primary_chapter = _infer_chapter_from_diagnoses(entities)
    excluded_chapters = UNRELATED_CHAPTER_PAIRS.get(primary_chapter, set()) if primary_chapter else set()

    log.info(
        "embedding_search_start",
        session_id=session_id,
        query_text=primary_text[:80],
        chapter_context=primary_chapter,
        excluded_chapters=list(excluded_chapters),
    )

    # Generate embedding
    try:
        query_vector = _embed_text(primary_text)
    except Exception as e:
        log.error("embedding_generation_failed", session_id=session_id, error=str(e))
        state["candidate_icd_codes"] = []
        state["mapping_path"] = "embedding_failed"
        return state

    # Query Supabase vector search via RPC
    # IMPORTANT: PostgREST requires vector as a string literal, not a Python list
    try:
        results = await rpc("match_icd_codes", {
            "query_embedding":      _vector_to_pg_literal(query_vector),
            "similarity_threshold": SIMILARITY_THRESHOLD,
            "match_count":          EMBEDDING_TOP_K + 5,
        })
    except Exception as e:
        log.error("embedding_rpc_failed", session_id=session_id, error=str(e))
        state["candidate_icd_codes"] = []
        state["mapping_path"] = "embedding_failed"
        return state

    log.info(
        "embedding_rpc_raw_results",
        session_id=session_id,
        raw_hits=len(results) if results else 0,
        threshold=SIMILARITY_THRESHOLD,
    )

    # Apply chapter exclusion guardrail
    filtered = [
        r for r in results
        if r.get("chapter") not in excluded_chapters
    ][:EMBEDDING_TOP_K]

    if not filtered:
        log.warning(
            "embedding_no_matches",
            session_id=session_id,
            query_text=primary_text[:80],
            raw_hits=len(results),
            after_filter=0,
        )
        state["candidate_icd_codes"] = []
        state["mapping_path"] = "no_mapping"
        return state

    # Format candidates to match same structure as Node 4 output
    candidates = []
    for r in filtered:
        candidates.append({
            "code":               r["code"],
            "description":        r["description"],
            "is_billable":        r.get("is_billable", True),
            "is_cc":              r.get("is_cc", False),
            "is_mcc":             r.get("is_mcc", False),
            "base_reimbursement": float(r.get("base_reimbursement", 0)),
            "icd_version":        r.get("version", "ICD-10-CM-2024"),
            # Embedding-specific fields
            "mapping_type":       "approximate",
            "confidence":         float(r.get("similarity", 0.70)),
            "is_primary":         False,    # Node 6 decides the best
            "source":             "embedding",
        })

    state["candidate_icd_codes"] = candidates
    state["mapping_path"]        = "embedding"

    log.info(
        "embedding_candidates_found",
        session_id=session_id,
        query_text=primary_text[:80],
        candidates_found=len(candidates),
        top_code=candidates[0]["code"] if candidates else None,
        top_similarity=candidates[0]["confidence"] if candidates else None,
        mapping_path="embedding",
    )

    return state
