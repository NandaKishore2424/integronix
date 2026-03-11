"""
This is the very first step in our process. This agent takes the initial
document, which can be a PDF or plain text, and gets it ready for the
rest of the pipeline by extracting the raw text content.
"""
from agents.graph import CodingState
from agents.node_runner import safe_node
from services.pdf_service import extract_text_from_pdf
from exceptions import PDFExtractionError


@safe_node("doc_processing")
async def doc_processing_node(state: CodingState) -> CodingState:
    # This is the first node in our LangGraph pipeline. Its job is to
    # get the raw text from either a PDF file or from direct input.

    # If the text is already here, we don't need to do anything.
    # This happens when a user pastes text directly into the application.
    if state.get("raw_text"):
        state.setdefault("document_source", "text_input")
        state.setdefault("ocr_used", False)
        return state

    # If we have a PDF, we'll use our PDF service to extract the text.
    pdf_bytes = state.get("pdf_bytes")
    if not pdf_bytes:
        # We can't proceed without either text or a PDF.
        raise PDFExtractionError(
            "Neither raw_text nor pdf_bytes found in state. "
            "Set one before invoking the graph."
        )

    # Extract the text — returns (text, ocr_used) tuple
    raw_text, ocr_used = extract_text_from_pdf(pdf_bytes)
    state["raw_text"] = raw_text
    state["document_source"] = "pdf_upload"
    state["ocr_used"] = ocr_used
    return state

