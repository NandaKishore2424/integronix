"""
agents/doc_processor.py — Node 1: Document Processing Node (Deterministic)
"""
from agents.graph import CodingState
from agents.node_runner import safe_node
from services.pdf_service import extract_text_from_pdf
from exceptions import PDFExtractionError


@safe_node("doc_processing")
async def doc_processing_node(state: CodingState) -> CodingState:
    """
    LangGraph Node 1 — Document Processing.
    Input:  state["pdf_bytes"]  OR  state["raw_text"] (pre-set via /code/run)
    Output: state["raw_text"]

    Pass-through: if raw_text is already in state, skip PDF extraction.
    This allows the /code/run endpoint to provide text directly.
    """
    # Pass-through: text already extracted or provided directly
    if state.get("raw_text"):
        return state

    pdf_bytes = state.get("pdf_bytes")
    if not pdf_bytes:
        raise PDFExtractionError(
            "Neither raw_text nor pdf_bytes found in state. "
            "Set one before invoking the graph."
        )

    raw_text = extract_text_from_pdf(pdf_bytes)
    state["raw_text"] = raw_text
    return state

