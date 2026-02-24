"""
agents/graph.py — LangGraph full pipeline: Nodes 1-8 (including Node 5 embedding fallback).

Flow:
  doc_processing → clinical_extract → snomed_resolve → snomed_icd_map
  → [conditional] → if direct: icd_decision
                  → if no_mapping: icd_embedding → icd_decision
  → audit_comparison → risk_scoring → END
"""
from typing import TypedDict, Optional, List


class CodingState(TypedDict, total=False):
    """Shared state object flowing through all LangGraph nodes."""
    # Identity
    session_id: str
    pdf_bytes: Optional[bytes]

    # Node 1 output
    raw_text: str

    # Node 2 output
    structured_entities: dict
    extraction_metadata: dict       # model, llm_version, tokens

    # Node 3 output
    resolved_snomed_code: Optional[str]
    resolved_snomed_desc: Optional[str]
    snomed_resolution_method: str   # llm_suggested | text_matched | not_found

    # Node 4 output
    direct_mapped_icd: Optional[str]
    mapping_path: str               # direct | no_mapping | no_snomed | embedding | embedding_failed
    candidate_icd_codes: List[dict]

    # Node 6 output
    final_icd_code: str
    confidence_score: float

    # Node 7 input/output
    human_icd_code: Optional[str]
    discrepancy_type: Optional[str]
    discrepancy: Optional[dict]
    financial_delta: Optional[float]

    # Node 8 output
    risk_score: float
    risk_label: str                 # LOW | MEDIUM | HIGH

    # Error tracing (set by @safe_node on failure)
    error_at: Optional[str]
    error_detail: Optional[str]


def _route_after_mapping(state: CodingState) -> str:
    """
    Conditional router after Node 4 (snomed_icd_map).
    If direct mapping found → go straight to deterministic ICD decision.
    If no mapping found    → go to embedding fallback (Node 5).
    """
    path = state.get("mapping_path", "no_mapping")
    has_candidates = bool(state.get("candidate_icd_codes"))

    if path == "direct" and has_candidates:
        return "icd_decision"
    return "icd_embedding"


def build_integronix_graph():
    """
    Builds and compiles the full LangGraph pipeline — all 8 nodes.

    Node 5 (embedding fallback) triggered via conditional edge:
      - mapping_path == "direct"    → skip Node 5, go directly to Node 6
      - mapping_path == "no_mapping" → go to Node 5, then Node 6
    """
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

    # ── Register all nodes ────────────────────────────────────────────────
    graph.add_node("doc_processing",   doc_processing_node)
    graph.add_node("clinical_extract", clinical_extraction_agent)
    graph.add_node("snomed_resolve",   snomed_resolver_node)
    graph.add_node("snomed_icd_map",   snomed_icd_mapping_node)
    graph.add_node("icd_embedding",    icd_embedding_node)   # Node 5
    graph.add_node("icd_decision",     icd_decision_node)    # Node 6
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
