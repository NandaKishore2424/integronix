"""
This agent uses a Large Language Model (LLM) to extract clinical entities
from the raw medical text. It's a critical first step in understanding the
patient's condition, pulling out diagnoses, symptoms, and procedures.
"""
from agents.graph import CodingState
from agents.node_runner import safe_node
from services.extraction_service import extract_clinical_entities


@safe_node("clinical_extract")
async def clinical_extraction_agent(state: CodingState) -> CodingState:
    # This is the second node in our LangGraph pipeline. It takes the raw text
    # from the previous step and uses an LLM to find clinical information.
    raw_text = state.get("raw_text", "")
    session_id = str(state.get("session_id", ""))

    # We can't do anything without the text, so we'll stop if it's missing.
    if not raw_text:
        raise ValueError("raw_text is empty — doc_processing_node must run first")

    # The extraction service handles the call to the LLM and returns a structured
    # list of clinical entities, plus some metadata about the process.
    extraction, metadata = await extract_clinical_entities(raw_text, session_id=session_id)

    # We'll add the results to our main state object to be used by the next nodes.
    state["structured_entities"] = extraction.model_dump()
    state["extraction_metadata"] = metadata
    return state
