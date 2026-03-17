# 17 — Updated LangGraph Node Structure (SNOMED-Aware)

## What Changed from Original Design

The original design went: `Extract → Retrieve ICD → Decide → Audit → Risk`

The SNOMED-aware design adds a resolution layer between extraction and ICD retrieval:

```
Extract → SNOMED Resolve → SNOMED→ICD Direct Map → (Fallback: Embedding) → Decide → Audit → Risk
```

This makes the system clinically correct — not just keyword-matching.

---

## Updated CodingState

```python
from typing import TypedDict, Optional, List

class CodingState(TypedDict):
    # === INPUT ===
    raw_text: str                        # Extracted text from PDF

    # === AFTER CLINICAL EXTRACTION ===
    structured_entities: dict            # FHIR-aligned dict:
                                         #   diagnoses[], severity, comorbidities[], evidence_text
                                         #   includes snomed_candidate per diagnosis

    # === AFTER SNOMED RESOLUTION ===
    resolved_snomed_code: Optional[str]  # Verified SNOMED code from snomed_concepts table
    resolved_snomed_desc: Optional[str]  # Description of resolved SNOMED concept
    snomed_resolution_method: str        # "llm_suggested" | "embedding_matched" | "not_found"

    # === AFTER SNOMED→ICD MAPPING ===
    direct_mapped_icd: Optional[str]     # ICD code from snomed_icd_map (if found)
    mapping_type: Optional[str]          # "exact" | "narrower" | "broader" | "approximate"
    mapping_path: str                    # "direct" | "embedding_fallback"

    # === AFTER ICD CANDIDATE RETRIEVAL (FALLBACK) ===
    candidate_icd_codes: List[dict]      # Top 5 candidates with similarity scores

    # === AFTER ICD DECISION ===
    final_icd_code: str                  # Selected, validated ICD-10 code
    confidence_score: float              # 0.0 – 1.0

    # === AUDIT INPUTS (OPTIONAL) ===
    human_icd_code: Optional[str]        # Human-assigned code

    # === AFTER AUDIT ===
    discrepancy: Optional[dict]          # Discrepancy analysis result

    # === AFTER FINANCIAL CALCULATION ===
    financial_delta: Optional[float]     # Revenue difference (AI vs Human)

    # === AFTER RISK SCORING ===
    risk_score: float                    # 0.0 = low risk, 1.0 = high risk
    risk_label: str                      # "LOW" | "MEDIUM" | "HIGH"
```

---

## Node Definitions

### NODE 1 — Document Processing Node
**Type:** Deterministic | **LLM:** No

```python
def doc_processing_node(state: CodingState) -> CodingState:
    """
    Extract raw text from PDF.
    Uses pdfplumber (primary) or pytesseract (OCR fallback for scanned PDFs).
    """
    # Input: PDF bytes passed via API
    # Output: state["raw_text"]
    pass
```

**Tools:** `pdfplumber`, `pytesseract` (OCR fallback)
**Output:** `state["raw_text"]`

---

### NODE 2 — Clinical Extraction Agent
**Type:** LLM (Groq) | **LLM:** YES — for clinical NLP only

**LLM Prompt Contract:**
```
System: You are a clinical coding assistant. Extract clinical entities from medical text.
        DO NOT generate ICD codes. DO NOT generate CPT codes.
        Return ONLY structured JSON.

User: [raw_text]

Return JSON matching this schema exactly:
{
  "diagnoses": [
    {
      "text": "string — clinical description",
      "severity": "mild | moderate | severe | acute | chronic",
      "laterality": "left | right | bilateral | null",
      "snomed_candidate": {
        "code": "SNOMED concept ID or null",
        "description": "SNOMED description or best clinical label"
      },
      "comorbidities": ["list of comorbid condition strings"],
      "evidence_text": "exact quote from source text supporting this diagnosis"
    }
  ],
  "observations": [
    {
      "loinc_description": "eGFR | creatinine | etc",
      "value": "numeric or string value",
      "unit": "unit string or null"
    }
  ]
}
```

**Pydantic Validation Schema:**
```python
from pydantic import BaseModel
from typing import Optional, List

class SnomedCandidate(BaseModel):
    code: Optional[str]
    description: str

class DiagnosisEntity(BaseModel):
    text: str
    severity: Optional[str]
    laterality: Optional[str]
    snomed_candidate: SnomedCandidate
    comorbidities: List[str] = []
    evidence_text: str

class ObservationEntity(BaseModel):
    loinc_description: str
    value: str
    unit: Optional[str]

class ExtractionResult(BaseModel):
    diagnoses: List[DiagnosisEntity]
    observations: List[ObservationEntity] = []
```

**Output:** `state["structured_entities"]`

---

### NODE 3 — SNOMED Concept Resolver
**Type:** Deterministic + Embedding fallback | **LLM:** No

```python
async def snomed_resolver_node(state: CodingState) -> CodingState:
    """
    Verify LLM-suggested SNOMED code exists in DB.
    If not, find best SNOMED match via embedding similarity.
    """
    candidate = state["structured_entities"]["diagnoses"][0]["snomed_candidate"]
    suggested_code = candidate.get("code")

    if suggested_code:
        # Check if it exists in snomed_concepts
        row = await db.fetchrow(
            "SELECT snomed_code, description FROM snomed_concepts WHERE snomed_code = $1 AND is_active = TRUE",
            suggested_code
        )
        if row:
            state["resolved_snomed_code"] = row["snomed_code"]
            state["resolved_snomed_desc"] = row["description"]
            state["snomed_resolution_method"] = "llm_suggested"
            return state

    # Fallback: Embedding similarity search on SNOMED concepts table
    diagnosis_text = state["structured_entities"]["diagnoses"][0]["text"]
    query_embedding = model.encode(diagnosis_text, normalize_embeddings=True)

    result = await db.fetchrow(
        """
        SELECT snomed_code, description
        FROM snomed_concepts
        WHERE is_active = TRUE
        ORDER BY embedding <=> $1::vector
        LIMIT 1
        """,
        json.dumps(query_embedding.tolist())
    )

    if result:
        state["resolved_snomed_code"] = result["snomed_code"]
        state["resolved_snomed_desc"] = result["description"]
        state["snomed_resolution_method"] = "embedding_matched"
    else:
        state["resolved_snomed_code"] = None
        state["snomed_resolution_method"] = "not_found"

    return state
```

**Output:** `state["resolved_snomed_code"]`, `state["snomed_resolution_method"]`

---

### NODE 4 — SNOMED → ICD Direct Mapping Node
**Type:** Deterministic | **LLM:** No

```python
async def snomed_icd_mapping_node(state: CodingState) -> CodingState:
    """
    Query snomed_icd_map for direct mapping.
    Sets direct_mapped_icd if found.
    Sets candidate_icd_codes from map results for use in decision node.
    """
    snomed_code = state.get("resolved_snomed_code")

    if not snomed_code:
        # No SNOMED resolved — skip to embedding fallback
        state["mapping_path"] = "embedding_fallback"
        state["direct_mapped_icd"] = None
        return state

    rows = await db.fetch(
        """
        SELECT sim.icd_code, sim.mapping_type, sim.confidence, sim.is_primary,
               ic.description, ic.is_cc, ic.is_mcc, ic.base_reimbursement
        FROM snomed_icd_map sim
        JOIN icd_codes ic ON ic.code = sim.icd_code
        WHERE sim.snomed_code = $1
          AND ic.is_billable = TRUE
        ORDER BY sim.confidence DESC
        """,
        snomed_code
    )

    if rows:
        # Build candidate pool from mapping table
        state["candidate_icd_codes"] = [
            {
                "code": row["icd_code"],
                "description": row["description"],
                "is_cc": row["is_cc"],
                "is_mcc": row["is_mcc"],
                "base_reimbursement": float(row["base_reimbursement"]),
                "similarity_score": float(row["confidence"]),
                "source": "snomed_map",
                "mapping_type": row["mapping_type"]
            }
            for row in rows
        ]
        state["mapping_path"] = "direct"
        # Primary mapping for exact types goes straight to decision
        primary = next((r for r in rows if r["is_primary"] and r["mapping_type"] == "exact"), None)
        state["direct_mapped_icd"] = primary["icd_code"] if primary else None
    else:
        state["mapping_path"] = "embedding_fallback"
        state["direct_mapped_icd"] = None
        state["candidate_icd_codes"] = []

    return state
```

**Routing after this node:**
```python
def route_after_snomed_mapping(state: CodingState) -> str:
    if state.get("candidate_icd_codes"):
        return "icd_decision"   # Candidates found — go to decision
    return "icd_embedding"      # No candidates — fall back to embedding search
```

---

### NODE 5 — ICD Embedding Retrieval (Fallback Only)
**Type:** Deterministic + pgvector | **LLM:** No

```python
async def icd_embedding_node(state: CodingState) -> CodingState:
    """
    Runs ONLY when SNOMED mapping finds nothing.
    Generates embedding from diagnosis + comorbidities text.
    Queries icd_codes.embedding for top 5 matches.
    """
    diagnosis = state["structured_entities"]["diagnoses"][0]
    query_text = f"{diagnosis['text']} {' '.join(diagnosis['comorbidities'])}".strip()
    query_embedding = model.encode(query_text, normalize_embeddings=True)

    rows = await db.fetch(
        """
        SELECT code, description, is_cc, is_mcc, base_reimbursement,
               1 - (embedding <=> $1::vector) AS similarity_score
        FROM icd_codes
        WHERE is_billable = TRUE AND embedding IS NOT NULL
        ORDER BY embedding <=> $1::vector
        LIMIT 5
        """,
        json.dumps(query_embedding.tolist())
    )

    state["candidate_icd_codes"] = [
        {
            "code": row["code"],
            "description": row["description"],
            "is_cc": row["is_cc"],
            "is_mcc": row["is_mcc"],
            "base_reimbursement": float(row["base_reimbursement"]),
            "similarity_score": float(row["similarity_score"]),
            "source": "embedding",
            "mapping_type": "approximate"
        }
        for row in rows
    ]
    state["mapping_path"] = "embedding_fallback"
    return state
```

---

### NODE 6 — Deterministic ICD Decision Node
**Type:** Deterministic algorithm | **LLM:** Partially (tiebreaker only)

See `18_deterministic_icd_algorithm.md` for the full algorithm definition.

**Output:** `state["final_icd_code"]`, `state["confidence_score"]`

---

### NODE 7 — Audit Comparison Agent (Conditional)
**Type:** Deterministic | **LLM:** No | **Triggered only if** `human_icd_code` is set

```python
async def audit_comparison_node(state: CodingState) -> CodingState:
    ai_code    = state["final_icd_code"]
    human_code = state["human_icd_code"]

    if ai_code == human_code:
        state["discrepancy"] = {"type": "EXACT_MATCH"}
        state["financial_delta"] = 0.0
        return state

    # Fetch reimbursements for both codes
    ai_reimb    = await get_reimbursement(ai_code)
    human_reimb = await get_reimbursement(human_code)
    delta = ai_reimb - human_reimb

    # Determine discrepancy type
    if not await code_exists_in_db(human_code):
        disc_type = "UNSUPPORTED_CODE"
    elif is_more_specific(ai_code, human_code):
        disc_type = "SPECIFICITY_IMPROVEMENT"
    elif is_more_specific(human_code, ai_code):
        disc_type = "OVERCODING"
    else:
        disc_type = "APPROXIMATE_MATCH"

    state["discrepancy"] = {
        "type": disc_type,
        "ai_code": ai_code,
        "human_code": human_code,
        "evidence": state["structured_entities"]["diagnoses"][0]["evidence_text"],
        "explanation": build_explanation(disc_type, ai_code, human_code)
    }
    state["financial_delta"] = delta
    return state
```

---

### NODE 8 — Risk Scoring Node
**Type:** Deterministic | **LLM:** No

```python
def risk_scoring_node(state: CodingState) -> CodingState:
    disc = state.get("discrepancy", {})
    disc_type = disc.get("type", "NO_COMPARISON")

    score_map = {
        "EXACT_MATCH":             (0.1, "LOW"),
        "APPROXIMATE_MATCH":       (0.3, "LOW"),
        "SPECIFICITY_IMPROVEMENT": (0.5, "MEDIUM"),
        "OVERCODING":              (0.85, "HIGH"),
        "UNSUPPORTED_CODE":        (0.95, "HIGH"),
        "NO_COMPARISON":           (0.2, "LOW"),
    }

    state["risk_score"], state["risk_label"] = score_map.get(disc_type, (0.2, "LOW"))
    return state
```

---

## Complete Graph Definition

```python
from langgraph.graph import StateGraph, END

def build_integronix_graph():
    graph = StateGraph(CodingState)

    graph.add_node("doc_processing",    doc_processing_node)
    graph.add_node("clinical_extract",  clinical_extraction_agent)
    graph.add_node("snomed_resolve",    snomed_resolver_node)
    graph.add_node("snomed_icd_map",    snomed_icd_mapping_node)
    graph.add_node("icd_embedding",     icd_embedding_node)
    graph.add_node("icd_decision",      icd_decision_node)
    graph.add_node("audit_comparison",  audit_comparison_node)
    graph.add_node("risk_scoring",      risk_scoring_node)

    graph.set_entry_point("doc_processing")

    graph.add_edge("doc_processing",   "clinical_extract")
    graph.add_edge("clinical_extract", "snomed_resolve")
    graph.add_edge("snomed_resolve",   "snomed_icd_map")

    # Conditional: direct mapping found → decision; else → embedding fallback
    graph.add_conditional_edges(
        "snomed_icd_map",
        lambda s: "icd_decision" if s.get("candidate_icd_codes") else "icd_embedding",
        {"icd_decision": "icd_decision", "icd_embedding": "icd_embedding"}
    )

    graph.add_edge("icd_embedding",  "icd_decision")

    # Conditional: audit if human code provided
    graph.add_conditional_edges(
        "icd_decision",
        lambda s: "audit_comparison" if s.get("human_icd_code") else "risk_scoring",
        {"audit_comparison": "audit_comparison", "risk_scoring": "risk_scoring"}
    )

    graph.add_edge("audit_comparison", "risk_scoring")
    graph.add_edge("risk_scoring",     END)

    return graph.compile()

app = build_integronix_graph()
```

---

## Execution Graph (Visual)

```
doc_processing
      │
clinical_extract
      │
snomed_resolve
      │
snomed_icd_map
      │
 ┌────┴────┐
 │         │
found    not found
 │         │
 │    icd_embedding
 │         │
 └────┬────┘
      │
icd_decision
      │
 ┌────┴────┐
has_human no_human
 │          │
audit   risk_scoring
 │          │
 └────┬─────┘
      │
    END
```
