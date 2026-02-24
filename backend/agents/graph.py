"""
agents/graph.py — LangGraph Orchestration: Full CodingState + Partial Graph

Nodes 1–3 are wired (Phase 3).
Nodes 4–8 are stubbed — will be fully implemented in Phase 4.
"""
from typing import TypedDict, Optional, List


class CodingState(TypedDict):
    """Shared state object that flows through all LangGraph nodes."""
    # Raw PDF bytes (set before graph.invoke)
    pdf_bytes: Optional[bytes]
    # Node 1 output
    raw_text: str
    # Node 2 output
    structured_entities: dict
    # Node 3 output
    resolved_snomed_code: Optional[str]
    resolved_snomed_desc: Optional[str]
    snomed_resolution_method: str
    # Node 4 output
    direct_mapped_icd: Optional[str]
    mapping_type: Optional[str]
    mapping_path: str
    candidate_icd_codes: List[dict]
    # Node 5/6 output
    final_icd_code: str
    confidence_score: float
    # Audit inputs
    human_icd_code: Optional[str]
    # Node 7 output
    discrepancy: Optional[dict]
    financial_delta: Optional[float]
    # Node 8 output
    risk_score: float
    risk_label: str


def build_integronix_graph():
    """
    Builds and compiles the full LangGraph pipeline.
    Phase 3: Nodes 1–3 wired. Phase 4 will add nodes 4–8.
    """
    from langgraph.graph import StateGraph, END
    from agents.doc_processor import doc_processing_node
    from agents.clinical_extractor import clinical_extraction_agent
    from agents.snomed_resolver import snomed_resolver_node

    graph = StateGraph(CodingState)

    # ── Phase 3 Nodes (implemented) ──────────────────────────────────────────
    graph.add_node("doc_processing",    doc_processing_node)
    graph.add_node("clinical_extract",  clinical_extraction_agent)
    graph.add_node("snomed_resolve",    snomed_resolver_node)

    graph.set_entry_point("doc_processing")
    graph.add_edge("doc_processing",   "clinical_extract")
    graph.add_edge("clinical_extract", "snomed_resolve")
    graph.add_edge("snomed_resolve",   END)

    # ── Phase 4 Nodes (to be added) ──────────────────────────────────────────
    # graph.add_node("snomed_icd_map",    snomed_icd_mapping_node)
    # graph.add_node("icd_embedding",     icd_embedding_node)
    # graph.add_node("icd_decision",      icd_decision_node)
    # graph.add_node("audit_comparison",  audit_comparison_node)
    # graph.add_node("risk_scoring",      risk_scoring_node)

    return graph.compile()
