# 11 — LangGraph: What It Is and How We Use It

## What LangGraph Is NOT

- Not a website or SaaS platform
- Not something you open in a browser
- Not an add-on to your frontend

## What LangGraph IS

**LangGraph is a Python library** — a backend orchestration framework for building:
- Stateful multi-step workflows
- Multi-agent pipelines
- Conditional routing logic
- Tool-calling pipelines

```bash
pip install langgraph
```

It lives entirely **inside our FastAPI backend.**

```
Next.js → FastAPI → LangGraph Workflow → PostgreSQL
```

---

## Why Normal LLM Apps Don't Work Here

A naive LLM app:
```
User → Prompt → LLM → Response
```

Our system needs:
- Multiple reasoning steps
- Conditional branching (audit only if human code exists)
- Tool calls (DB lookup, vector search)
- Persistent state across steps
- Retry logic and structured output validation

LangGraph provides all of this as a **directed graph of agent nodes**.

---

## Mental Model

| Component | Role |
|---|---|
| FastAPI | The highway — routes HTTP requests |
| LangGraph | The traffic controller — decides flow |
| LLM (Groq) | The brain — clinical reasoning |
| PostgreSQL | The knowledge vault — ICD codes, audit logs |
| pgvector | The memory — semantic similarity |

---

## The 3 Core Primitives You Define

### 1. State Object
Shared data that flows through every node.
```python
class CodingState(TypedDict):
    raw_text: str
    structured_entities: dict
    candidate_icd_codes: list
    final_icd_code: str
    human_icd_code: Optional[str]
    discrepancy: Optional[dict]
    financial_delta: Optional[float]
    risk_score: float
```

### 2. Nodes (Agent Functions)
Each node reads state, does work, writes back to state.
```python
def clinical_extraction_agent(state: CodingState) -> CodingState:
    # Call LLM, parse result, validate with Pydantic
    state["structured_entities"] = extracted_data
    return state
```

### 3. Edges (Flow Between Nodes)
Linear:
```python
graph.add_edge("extract", "retrieve")
```

Conditional:
```python
def route_after_decision(state):
    if state.get("human_icd_code"):
        return "audit"
    return "risk_scoring"

graph.add_conditional_edges("decide", route_after_decision, {...})
```

---

## Integronix Graph Definition (Skeleton)

```python
from langgraph.graph import StateGraph, END

graph = StateGraph(CodingState)

graph.add_node("doc_processing",        doc_processing_node)
graph.add_node("clinical_extraction",   clinical_extraction_agent)
graph.add_node("icd_retrieval",         icd_retrieval_node)
graph.add_node("icd_decision",          icd_decision_agent)
graph.add_node("audit_comparison",      audit_comparison_agent)
graph.add_node("risk_scoring",          risk_scoring_node)

graph.set_entry_point("doc_processing")

graph.add_edge("doc_processing",      "clinical_extraction")
graph.add_edge("clinical_extraction", "icd_retrieval")
graph.add_edge("icd_retrieval",       "icd_decision")

graph.add_conditional_edges(
    "icd_decision",
    lambda s: "audit_comparison" if s.get("human_icd_code") else "risk_scoring",
    {"audit_comparison": "audit_comparison", "risk_scoring": "risk_scoring"}
)

graph.add_edge("audit_comparison", "risk_scoring")
graph.add_edge("risk_scoring", END)

app = graph.compile()
```

---

## Important: LangGraph Does NOT Make You Agentic Automatically

YOU define:
- Which nodes use LLM (only clinical extraction + decision assist)
- Which nodes are deterministic (doc processing, retrieval, risk scoring)
- Which nodes use tools (DB lookup, pgvector search)

LangGraph just gives you the orchestration structure.

---

## What to Say When Asked About LangGraph

> *"We use LangGraph for stateful multi-agent orchestration. It allows us to structure clinical extraction, deterministic ICD mapping, audit comparison, and risk scoring as separate agent nodes operating on shared state with conditional routing. This prevents us from building a single monolithic LLM call and gives us clear, testable boundaries between reasoning and deterministic logic."*

---

## LangGraph vs LangChain (Why We Chose LangGraph)

| Feature | LangChain | LangGraph |
|---|---|---|
| Linear chains | ✅ Good | ✅ Good |
| Conditional branching | ❌ Awkward | ✅ Native |
| Stateful graph execution | ❌ No | ✅ Yes |
| Multi-node orchestration | ❌ Messy | ✅ Clean |
| Retry logic per node | ❌ Limited | ✅ Built-in |

Our workflow is non-linear (audit branch). LangGraph is the correct choice.
