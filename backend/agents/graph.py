"""
graph.py — LangGraph Orchestration Entry Point
Stub file: full implementation added in Phase 4.
"""

from typing import TypedDict, Optional, List


class CodingState(TypedDict):
    """Shared state object that flows through all LangGraph nodes."""
    # Input
    raw_text: str
    # After clinical extraction
    structured_entities: dict
    # After SNOMED resolution
    resolved_snomed_code: Optional[str]
    resolved_snomed_desc: Optional[str]
    snomed_resolution_method: str
    # After SNOMED→ICD mapping
    direct_mapped_icd: Optional[str]
    mapping_type: Optional[str]
    mapping_path: str
    # After ICD candidate retrieval
    candidate_icd_codes: List[dict]
    # After ICD decision
    final_icd_code: str
    confidence_score: float
    # Audit
    human_icd_code: Optional[str]
    discrepancy: Optional[dict]
    financial_delta: Optional[float]
    # Risk
    risk_score: float
    risk_label: str


# TODO Phase 4: Import and wire LangGraph nodes here
# from agents.doc_processor import doc_processing_node
# from agents.clinical_extractor import clinical_extraction_agent
# from agents.snomed_resolver import snomed_resolver_node
# from agents.snomed_icd_mapper import snomed_icd_mapping_node
# from agents.icd_embedding import icd_embedding_node
# from agents.icd_decision import icd_decision_node
# from agents.audit_agent import audit_comparison_node
# from agents.risk_scorer import risk_scoring_node
