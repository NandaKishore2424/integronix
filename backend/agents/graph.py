"""
This file defines the heart of our application: the LangGraph pipeline.
It connects all the individual agents (nodes) into a coherent workflow,
managing the flow of data from one step to the next. It also includes
the conditional logic that decides which path to take based on the data.
"""
from typing import TypedDict, Optional, List


class CodingState(TypedDict, total=False):
    # This is the shared memory or "state" that gets passed between all the
    # nodes in our graph. Each agent reads from and writes to this object.
    # Think of it as the patient's chart that gets updated at each station.

    # --- Input Data ---
    session_id: str
    pdf_bytes: Optional[bytes]
    human_icd_code: Optional[str] # The code entered by a human for comparison

    # --- Document metadata (set by Node 1) ---
    document_source: Optional[str]  # "text_input" | "pdf_upload"
    ocr_used: Optional[bool]        # True if Tesseract OCR fallback was triggered

    # --- Pipeline Data ---
    raw_text: str                   # Output from Node 1
    structured_entities: dict       # Output from Node 2 (the LLM)
    extraction_metadata: dict       # Info about the LLM call
    resolved_snomed_code: Optional[str] # Output from Node 3
    resolved_snomed_desc: Optional[str]
    snomed_resolution_method: str
    direct_mapped_icd: Optional[str]    # Output from Node 4
    mapping_path: str
    candidate_icd_codes: List[dict]
    final_icd_code: str             # Output from Node 6 (the final decision)
    confidence_score: float
    icd_codes: List[dict]

    # --- Audit & Risk Analysis ---
    discrepancy_type: Optional[str] # Output from Node 7
    discrepancy: Optional[dict]
    financial_delta: Optional[float]
    drg_flag: Optional[str]
    risk_score: float               # Output from Node 8
    risk_label: str

    # --- Final Outputs ---
    fhir_condition: Optional[dict]  # A standardized FHIR representation

    # --- Error Handling ---
    error_at: Optional[str]         # If a node fails, its name goes here
    error_detail: Optional[str]     # The error message


def _route_after_mapping(state: CodingState) -> str:
    # This is a conditional router. After we try to map SNOMED to ICD-10,
    # this function decides where to go next.
    path = state.get("mapping_path", "no_mapping")
    has_candidates = bool(state.get("candidate_icd_codes"))

    # If we found a direct, official mapping, we can go straight to the final decision.
    if path == "direct" and has_candidates:
        return "icd_decision"
    # Otherwise, we need to use our backup plan: vector search.
    return "icd_embedding"


def build_integronix_graph():
    # This function constructs the entire agent pipeline using LangGraph.
    # It defines all the nodes and the connections (edges) between them.
    from langgraph.graph import StateGraph, END
    from agents.doc_processor       import doc_processing_node
    from agents.clinical_extractor  import clinical_extraction_agent
    from agents.snomed_resolver     import snomed_resolver_node
    from agents.snomed_icd_mapper   import snomed_icd_mapping_node
    from agents.icd_embedding       import icd_embedding_node
    from agents.icd_decision        import icd_decision_node
    from agents.audit_comparison    import audit_comparison_node
    from agents.risk_scoring        import risk_scoring_node

    graph = StateGraph(CodingState)

    # First, we register each of our agent functions as a node in the graph.
    graph.add_node("doc_processing",   doc_processing_node)
    graph.add_node("clinical_extract", clinical_extraction_agent)
    graph.add_node("snomed_resolve",   snomed_resolver_node)
    graph.add_node("snomed_icd_map",   snomed_icd_mapping_node)
    graph.add_node("icd_embedding",    icd_embedding_node)   # Fallback: vector search
    graph.add_node("icd_decision",     icd_decision_node)    # Deterministic rule engine
    graph.add_node("audit_comparison", audit_comparison_node)
    graph.add_node("risk_scoring",     risk_scoring_node)

    # ── Wire the pipeline ─────────────────────────────────────────────────
    graph.set_entry_point("doc_processing")
    graph.add_edge("doc_processing",   "clinical_extract")
    graph.add_edge("clinical_extract", "snomed_resolve")
    graph.add_edge("snomed_resolve",   "snomed_icd_map")

    # Conditional: direct mapping → Node 6 | no mapping → Node 5 → Node 6
    graph.add_conditional_edges(
        "snomed_icd_map",
        _route_after_mapping,
        {
            "icd_decision":  "icd_decision",   # Direct path
            "icd_embedding": "icd_embedding",  # Fallback path
        },
    )
    graph.add_edge("icd_embedding",    "icd_decision")   # Node 5 → always goes to Node 6
    graph.add_edge("icd_decision",     "audit_comparison")
    graph.add_edge("audit_comparison", "risk_scoring")
    graph.add_edge("risk_scoring",     END)

    return graph.compile()
