"""
agents/doc_processor.py — Node 1: Document Processing Node (Deterministic)

Accepts PDF bytes from state and extracts raw text.
No LLM. Pure deterministic extraction.
"""
from agents.graph import CodingState
from services.pdf_service import extract_text_from_pdf


async def doc_processing_node(state: CodingState) -> CodingState:
    """
    LangGraph Node 1 — Document Processing.
    Input:  state["pdf_bytes"]   (bytes — set by the API before invoking graph)
    Output: state["raw_text"]
    """
    pdf_bytes = state.get("pdf_bytes")
    if not pdf_bytes:
        raise ValueError("pdf_bytes missing from state")

    raw_text = extract_text_from_pdf(pdf_bytes)
    state["raw_text"] = raw_text
    return state
