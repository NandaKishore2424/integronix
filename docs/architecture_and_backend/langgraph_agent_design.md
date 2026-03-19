# LangGraph Agent Design

## Design Philosophy

Our system's intelligence is not derived from a single, monolithic Large Language Model (LLM). Instead, we embrace a true agentic AI architecture, which we define as a system composed of multiple specialized agents, a shared state, the ability to use tools, and conditional routing. This is the core principle behind our choice of LangGraph.

LangGraph is superior to simpler chaining libraries for our needs because our workflow is a **cyclical graph**, not a straight line. We require:
- **Conditional Routing**: The path the data takes must change based on the context. For example, if an organization is configured for ICD-11, we call the WHO API; otherwise, we use our local SNOMED-to-ICD-10 mapping. If those primary paths fail, we must then route to a fallback vector search.
- **Stateful Execution**: A shared `CodingState` object is passed between all nodes. This object acts as the "memory" of the workflow, accumulating data from each step, from the initial raw text to the final financial impact analysis.
- **Modularity and Specialization**: Each node in the graph is a specialized agent with a single, well-defined responsibility. This makes the system highly modular, easier to debug, test, and upgrade.

---

## The `CodingState` Object: Shared Memory

This is the central data structure that flows through the entire graph. It's a Python `TypedDict` that acts as the shared memory for all agents. Each node reads from this state and writes its results back to it.

```python
# A simplified representation of the CodingState from backend/agents/graph.py

class CodingState(TypedDict, total=False):
    # --- Inputs & Configuration ---
    session_id: str
    org_id: Optional[str]
    icd_version: Optional[str]      # e.g., "icd-11" or "icd-10"
    claim_scheme: Optional[str]     # e.g., "ayushman", "cghs"
    human_icd_code: Optional[str]   # For audit comparison
    pdf_bytes: Optional[bytes]      # Raw PDF data if uploaded

    # --- Core Pipeline Data ---
    raw_text: str                   # Populated by Node 1
    structured_entities: dict       # Populated by Node 2 (LLM output)
    cpt_codes: List[dict]           # Populated by CPT Resolver Node
    snomed_concepts: List[dict]     # Populated by SNOMED Resolver Node
    candidate_icd_codes: List[dict] # Populated by Mapping/Embedding Nodes
    final_icd_code: str             # Populated by Decision Node
    confidence_score: float
    mapping_path: str               # "who_api", "snomed_to_icd_map", "embedding_search"
    decision_trace: Optional[dict]  # Explanation from the decision engine

    # --- Audit & Financials ---
    discrepancy: Optional[dict]
    financial_delta: Optional[float]
    risk_score: float
    risk_label: str
    financial_summary: Optional[dict]

    # --- Error Handling ---
    error_at: Optional[str]         # Name of the node that failed
```

---

## The Agentic Pipeline: Node Definitions

The pipeline is a directed acyclic graph with 10 specialized nodes.

**[View Full Pipeline Diagram](./diagrams.md#3-agent-architecture-diagram-langgraph-pipeline)**

### 1. `doc_processing_node`
- **Type**: Deterministic
- **Responsibility**: Text extraction. It takes raw `pdf_bytes` from the state and populates the `raw_text` field. It intelligently handles both digital and scanned PDFs by trying `pdfplumber` first and falling back to Tesseract OCR if necessary. It also sets metadata like `document_source` and `ocr_used`.

### 2. `clinical_extraction_agent`
- **Type**: LLM-Powered
- **Responsibility**: Clinical reasoning. This is one of the few places an LLM is used. It takes the `raw_text` and sends it to the Groq API with a carefully engineered prompt, instructing it to extract key clinical entities (diagnosis, comorbidities, procedures, etc.) and return them as a structured JSON object. The output is validated against a Pydantic model before being written to `state["structured_entities"]`.

### 3. `cpt_resolver_node`
- **Type**: Deterministic (Vector Search)
- **Responsibility**: CPT code resolution. It takes the extracted procedures and services from the LLM, generates vector embeddings, and performs a semantic search against a `pgvector` table of CPT codes to find the most relevant matches.

### 4. `snomed_resolver_node`
- **Type**: Hybrid (LLM + Deterministic Routing)
- **Responsibility**: Concept resolution and primary routing. This is a critical node.
    1.  It first checks `state["icd_version"]`.
    2.  **If ICD-11**: It calls the `who_icd_service` to directly query the WHO API. If successful, it populates `state["candidate_icd_codes"]` and sets `mapping_path` to `"who_api"`.
    3.  **If ICD-10**: It uses an LLM to resolve the clinical text to a SNOMED-CT concept ID.
- The output is a list of resolved SNOMED concepts written to `state["snomed_concepts"]`.

### 5. `snomed_icd_mapping_node`
- **Type**: Deterministic (Database Lookup)
- **Responsibility**: Direct crosswalking. This node is only active in the ICD-10 path. It takes the SNOMED concepts from the previous node and performs a direct lookup in the `snomed_icd_map` table in our PostgreSQL database to find corresponding ICD-10 codes. If found, it populates `state["candidate_icd_codes"]`.

### 6. `icd_embedding_node` (Fallback)
- **Type**: Deterministic (Vector Search)
- **Responsibility**: Semantic search fallback. This node is **only executed if** the previous mapping nodes (`who_api` or `snomed_icd_map`) failed to produce any candidate codes. It generates a vector embedding from the clinical summary and uses `pgvector` to find the top 5 most semantically similar ICD codes from our database. It sets `mapping_path` to `"embedding_search"`.

### 7. `icd_decision_node`
- **Type**: Deterministic (Rule-Based Engine)
- **Responsibility**: Final code selection. This node is the core of our "no hallucinations" promise. It takes the `candidate_icd_codes` (from whichever path they originated) and applies a sophisticated, rule-based scoring algorithm. It considers factors like code specificity, evidence from the clinical text, and negation penalties. It does **not** use an LLM. It selects the highest-scoring code and writes it to `state["final_icd_code"]`.

### 8. `audit_comparison_node`
- **Type**: Deterministic
- **Responsibility**: Compares the AI's `final_icd_code` with the `human_icd_code` (if provided). It categorizes the result (e.g., `SPECIFICITY_IMPROVEMENT`, `UNSUPPORTED_CODE`) and populates the `discrepancy` field.

### 9. `risk_scoring_node`
- **Type**: Deterministic
- **Responsibility**: Calculates a compliance risk score based on the audit results. For example, an `UNSUPPORTED_CODE` discrepancy results in a high risk score, while a `SPECIFICITY_IMPROVEMENT` is medium risk. The result is written to `state["risk_score"]` and `state["risk_label"]`.

### 10. `financial_calculator_node`
- **Type**: Deterministic
- **Responsibility**: Calculates the financial impact. It looks up the DRG/reimbursement values for both the AI and human codes and calculates the delta, writing it to `state["financial_summary"]`.

---

## Conditional Graph Flow

The logic for routing is defined in `backend/agents/graph.py`. The most critical conditional edge is the one that determines whether to use the vector search fallback.

```python
# backend/agents/graph.py

def _route_after_mapping(state: CodingState) -> str:
    """
    This function is a conditional edge in the graph.
    It checks if any previous node has already found candidate codes.
    """
    if state.get("candidate_icd_codes"):
        # If candidates exist (from WHO API or SNOMED map), go straight to the decision node.
        return "icd_decision"
    else:
        # If no candidates were found, trigger the embedding search fallback.
        return "icd_embedding"

# --- Graph Definition ---
graph = StateGraph(CodingState)

# ... (all nodes are added) ...

graph.set_entry_point("doc_processing")
graph.add_edge("doc_processing", "clinical_extract")
graph.add_edge("clinical_extract", "cpt_resolve")
graph.add_edge("cpt_resolve", "snomed_resolve")
graph.add_edge("snomed_resolve", "snomed_icd_map")

# This is where the conditional routing happens:
graph.add_conditional_edges(
    "snomed_icd_map",
    _route_after_mapping,
    {
        "icd_decision": "icd_decision",     # Path if candidates were found
        "icd_embedding": "icd_embedding",   # Path if no candidates were found
    }
)

graph.add_edge("icd_embedding", "icd_decision") # The fallback path rejoins the main flow
graph.add_edge("icd_decision", "audit_comparison")
graph.add_edge("audit_comparison", "risk_scoring")
graph.add_edge("risk_scoring", "financial_calc")
graph.add_edge("financial_calc", END)

# The compiled graph is a runnable object
app = graph.compile()
```

This structure ensures a robust, multi-path system that prioritizes direct, accurate methods but gracefully falls back to powerful semantic search when needed, all while maintaining a clear, auditable, and deterministic final decision process.

