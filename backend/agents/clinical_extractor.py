"""
agents/clinical_extractor.py — Node 2: Clinical Extraction Agent (LLM)

Calls Groq LLM to extract diagnoses + SNOMED candidates from raw text.
LLM output is validated via Pydantic before updating state.
"""
from agents.graph import CodingState
from services.extraction_service import extract_clinical_entities


async def clinical_extraction_agent(state: CodingState) -> CodingState:
    """
    LangGraph Node 2 — Clinical Extraction Agent.
    Input:  state["raw_text"]
    Output: state["structured_entities"]
    """
    raw_text = state.get("raw_text", "")
    if not raw_text:
        raise ValueError("raw_text is empty — doc_processing_node must run first")

    extraction = await extract_clinical_entities(raw_text)

    state["structured_entities"] = extraction.model_dump()
    return state
