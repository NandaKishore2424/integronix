"""
agents/clinical_extractor.py — Node 2: Clinical Extraction Agent (LLM)
"""
from agents.graph import CodingState
from agents.node_runner import safe_node
from services.extraction_service import extract_clinical_entities


@safe_node("clinical_extract")
async def clinical_extraction_agent(state: CodingState) -> CodingState:
    """
    LangGraph Node 2 — Clinical Extraction Agent.
    Input:  state["raw_text"]
    Output: state["structured_entities"], state["extraction_metadata"]
    """
    raw_text = state.get("raw_text", "")
    session_id = str(state.get("session_id", ""))

    if not raw_text:
        raise ValueError("raw_text is empty — doc_processing_node must run first")

    extraction, metadata = await extract_clinical_entities(raw_text, session_id=session_id)

    state["structured_entities"] = extraction.model_dump()
    state["extraction_metadata"] = metadata
    return state
