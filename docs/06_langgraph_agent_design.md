# 06 — LangGraph Agent Design

## Design Philosophy

> Real agentic AI = Multiple specialized agents + Shared state + Tool usage + Conditional routing.
> NOT a single LLM call with "Agent" in the function name.

LangGraph is chosen over LangChain because:
- Our workflow is **graph-based** (not linear)
- We need **conditional routing** (audit only if human code provided)
- We need **stateful execution** across multiple steps
- We need **retry logic** and resilience

---

## Global State Object

All agents read from and write to a shared `CodingState` object.

```python
from typing import TypedDict, Optional

class CodingState(TypedDict):
    # Input
    raw_text: str                    # Extracted text from PDF

    # After Clinical Extraction Agent
    structured_entities: dict        # Diagnosis, severity, comorbidities, evidence

    # After ICD Candidate Retrieval
    candidate_icd_codes: list        # Top 5 candidate ICD codes from DB

    # After ICD Decision Agent
    final_icd_code: str              # Selected best code
    confidence_score: float          # Match confidence (0.0 - 1.0)

    # Audit inputs (optional)
    human_icd_code: Optional[str]    # Human-assigned code (if audit mode)

    # After Audit Agent
    discrepancy: Optional[dict]      # Discrepancy analysis result

    # After Financial Intelligence Agent
    financial_delta: Optional[float] # Revenue delta (simulated)

    # After Risk Scoring Node
    risk_score: float                # Risk level: 0.0 = low, 1.0 = high
    risk_label: str                  # "LOW" | "MEDIUM" | "HIGH"
```

---

## Node Definitions

### NODE 1: Document Processing Node

**Type:** Deterministic (no LLM)
**Input:** `raw_pdf_bytes`
**Output:** `state["raw_text"]`

```
Responsibilities:
- Accept PDF bytes
- Use pdfplumber or PyMuPDF to extract text
- Handle scanned PDFs with OCR if needed
- Store raw text in state
```

**Tools used:** `pdf_extractor`, `ocr_tool`

---

### NODE 2: Clinical Extraction Agent (LLM Node)

**Type:** Agentic (LLM-powered)
**Input:** `state["raw_text"]`
**Output:** `state["structured_entities"]`

```
Responsibilities:
- Send raw text to LLM via Groq
- Extract: diagnosis, severity, chronic/acute, comorbidities, evidence text
- Force structured JSON output using Pydantic schema
- Validate output before writing to state
```

**LLM Prompt Constraint:**
> "Extract clinical entities only. DO NOT generate ICD codes. Return only: diagnosis, severity, laterality, comorbidities, and evidence_text."

**Output schema:**
```json
{
  "diagnosis": "Type 2 Diabetes with diabetic peripheral neuropathy",
  "severity": "moderate",
  "laterality": null,
  "comorbidities": ["hypertension", "chronic kidney disease stage 3"],
  "evidence_text": "Patient presents with bilateral foot pain and numbness..."
}
```

**Tools used:** `groq_llm`, `pydantic_validator`

---

### NODE 3: ICD Candidate Retrieval Node

**Type:** Deterministic (pgvector + DB)
**Input:** `state["structured_entities"]["diagnosis"]`
**Output:** `state["candidate_icd_codes"]`

```
Responsibilities:
- Generate embedding of extracted diagnosis text
- Query pgvector to find top 5 semantically similar ICD codes
- Return code details: code, description, billable flag, CC/MCC flag
```

**Tools used:** `embedding_model`, `pgvector_search`, `icd_db_lookup`

**Example output:**
```json
[
  {"code": "E11.22", "description": "Type 2 diabetes mellitus with diabetic chronic kidney disease, stage 3", "is_billable": true, "is_cc": true},
  {"code": "E11.40", "description": "Type 2 diabetes mellitus with diabetic neuropathy, unspecified", "is_billable": true, "is_cc": false},
  ...
]
```

---

### NODE 4: ICD Decision Agent (Hybrid Node)

**Type:** Hybrid (LLM reasoning + deterministic validation)
**Input:** `state["candidate_icd_codes"]`, `state["structured_entities"]`
**Output:** `state["final_icd_code"]`, `state["confidence_score"]`

```
Responsibilities:
- Present top 5 candidates to LLM
- LLM reasons about best match given severity and comorbidities
- Deterministic validator confirms:
    - Code exists in DB
    - Code is billable
    - Code matches specificity level
- If validation fails → select next best candidate
```

**Key Rule:**
> LLM SUGGESTS. Deterministic engine CONFIRMS.
> LLM cannot override DB validation.

**Tools used:** `groq_llm`, `billable_validator`, `specificity_checker`

---

### NODE 5: Audit Comparison Agent

**Type:** Agentic (conditional — only triggered if `human_icd_code` is provided)
**Input:** `state["final_icd_code"]`, `state["human_icd_code"]`, `state["structured_entities"]`
**Output:** `state["discrepancy"]`, `state["financial_delta"]`

```
Responsibilities:
- Compare AI code vs human code
- Determine discrepancy type:
    - EXACT_MATCH — codes match
    - SPECIFICITY_IMPROVEMENT — AI code is more specific
    - UNSUPPORTED_CODE — human code not backed by clinical text
    - OVERCODING — human code more specific than evidence supports
- Search clinical text for evidence supporting AI code
- Look up revenue delta from revenue_lookup table
```

**Discrepancy output:**
```json
{
  "type": "SPECIFICITY_IMPROVEMENT",
  "ai_code": "E11.22",
  "human_code": "E11.9",
  "explanation": "AI identified chronic kidney disease stage 3 from clinical text",
  "evidence": "Patient has CKD stage 3 as documented in labs section",
  "revenue_delta": 450.00
}
```

**Tools used:** `icd_db_comparison`, `evidence_search`, `revenue_lookup`

---

### NODE 6: Risk Scoring Node

**Type:** Deterministic
**Input:** `state["discrepancy"]` (if exists), `state["final_icd_code"]`
**Output:** `state["risk_score"]`, `state["risk_label"]`

```
Risk Rules:
- EXACT_MATCH → risk_score = 0.1, label = "LOW"
- SPECIFICITY_IMPROVEMENT → risk_score = 0.5, label = "MEDIUM"
  (missed revenue, potential audit if undercoded systematically)
- UNSUPPORTED_CODE → risk_score = 0.9, label = "HIGH"
  (compliance risk — billing unsupported by documentation)
- OVERCODING → risk_score = 0.95, label = "HIGH"
  (fraud risk)
- No human code provided → risk_score = 0.2, label = "LOW"
```

**Tools used:** None (pure logic)

---

## Conditional Graph Flow

```python
from langgraph.graph import StateGraph, END

graph = StateGraph(CodingState)

# Add nodes
graph.add_node("doc_processing", doc_processing_node)
graph.add_node("clinical_extraction", clinical_extraction_agent)
graph.add_node("icd_retrieval", icd_retrieval_node)
graph.add_node("icd_decision", icd_decision_agent)
graph.add_node("audit_comparison", audit_comparison_agent)
graph.add_node("risk_scoring", risk_scoring_node)

# Define edges
graph.set_entry_point("doc_processing")
graph.add_edge("doc_processing", "clinical_extraction")
graph.add_edge("clinical_extraction", "icd_retrieval")
graph.add_edge("icd_retrieval", "icd_decision")

# Conditional routing: audit if human_icd_code is provided
def route_after_decision(state: CodingState):
    if state.get("human_icd_code"):
        return "audit_comparison"
    return "risk_scoring"

graph.add_conditional_edges(
    "icd_decision",
    route_after_decision,
    {
        "audit_comparison": "audit_comparison",
        "risk_scoring": "risk_scoring"
    }
)

graph.add_edge("audit_comparison", "risk_scoring")
graph.add_edge("risk_scoring", END)

app = graph.compile()
```

---

## Why This is Real Agentic AI (For Q&A)

| Agentic Criterion | Present in Our Design? |
|---|---|
| Multiple specialized agents | ✅ Yes — 6 distinct nodes |
| Shared persistent state | ✅ Yes — CodingState |
| Tool usage by agents | ✅ Yes — DB, pgvector, LLM, validators |
| Conditional routing | ✅ Yes — audit branch |
| Reasoning under uncertainty | ✅ Yes — ICD Decision Agent |
| Deterministic guardrails | ✅ Yes — code validation, billable check |

---

## Where LLM Is Used vs Where It's Forbidden

| Node | LLM Allowed? | Reason |
|---|---|---|
| Document Processing | ❌ No | Pure file extraction |
| Clinical Extraction | ✅ Yes | Clinical NLP reasoning |
| ICD Candidate Retrieval | ❌ No | DB + vector search only |
| ICD Decision | ✅ Partially | Reasoning among candidates only |
| Audit Comparison | ❌ No | Rule-based comparison |
| Risk Scoring | ❌ No | Pure logic |

---

## Pitch Explanation (Memorize This)

> *"We implemented a LangGraph-based multi-agent workflow where specialized agents perform clinical extraction, deterministic ICD candidate retrieval, reasoning-based selection, audit comparison, and risk scoring. Agents interact with internal tools such as ICD master database and revenue lookup tables, ensuring explainability and preventing hallucinated outputs."*
