"""
This agent assumes the responsibility of matching extracted medical procedures
to official CMS CPT/HCPCS codes via semantic vector search.
"""
import os
from dotenv import load_dotenv
from supabase import create_client, Client
from sentence_transformers import SentenceTransformer
from agents.graph import CodingState
from agents.node_runner import safe_node
from logger import get_logger

load_dotenv()
log = get_logger(__name__)

# Load model globally to keep the LangGraph pipeline fast across multiple calls
try:
    _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
except Exception as e:
    log.error(f"Failed to load sentence transformer model: {e}")
    _embedding_model = None

@safe_node("cpt_resolve")
async def cpt_resolver_node(state: CodingState) -> CodingState:
    session_id = str(state.get("session_id", ""))
    procedures = state.get("procedures_and_services", [])
    
    # Check if Groq found any procedures
    if not procedures:
        log.info("cpt_resolve_skipped", session_id=session_id, reason="no procedures extracted")
        state["cpt_codes"] = []
        return state

    if not _embedding_model:
        log.error("cpt_resolve_failed", session_id=session_id, reason="model not loaded")
        state["cpt_codes"] = []
        return state

    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        log.error("cpt_resolve_failed", session_id=session_id, reason="supabase credentials missing")
        state["cpt_codes"] = []
        return state

    supabase: Client = create_client(url, key)
    all_cpt_matches = []

    for procedure_text in procedures:
        try:
            # 1. Generate the semantic vector for the doctor's text
            embedding_vector = _embedding_model.encode(procedure_text).tolist()
            
            # 2. Query our custom Supabase RPC for a semantic search
            response = supabase.rpc(
                "match_cpt_codes",
                {
                    "query_embedding": embedding_vector,
                    "match_threshold": 0.55, # Minimum confidence threshold
                    "match_count": 1         # Get the single best matched standard code
                }
            ).execute()
            
            matches = response.data
            if matches and len(matches) > 0:
                best_match = matches[0]
                all_cpt_matches.append({
                    "original_text": procedure_text,
                    "code": best_match["code"],
                    "description": best_match["description"],
                    "type": best_match["code_type"],
                    "base_price": float(best_match["base_price"]),
                    "confidence": float(best_match["similarity"])
                })
                log.info("cpt_matched", session_id=session_id, original=procedure_text, code=best_match["code"], confidence=best_match["similarity"])
            else:
                log.warning("cpt_no_match", session_id=session_id, original=procedure_text)
                
        except Exception as e:
            log.error("cpt_resolve_error", session_id=session_id, error=str(e), procedure=procedure_text)

    state["cpt_codes"] = all_cpt_matches
    return state
