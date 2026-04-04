# Vector Embedding Pipeline for Semantic Search

## 1. Purpose

The vector embedding pipeline serves as a critical **fallback mechanism** in our agentic workflow. When the primary, high-precision mapping paths (e.g., WHO API or direct SNOMED-to-ICD crosswalk) fail to produce candidate codes, the system uses semantic vector search to find the most clinically similar ICD codes from our database.

This ensures robustness, guaranteeing that the system can provide relevant suggestions even for ambiguous or poorly defined clinical text. This process is powered by the `pgvector` extension in our Supabase PostgreSQL database.

---

## 2. The Embedding Model

To ensure consistency between the data at rest and the data at runtime, we use the same embedding model throughout the entire pipeline.

-   **Model**: `sentence-transformers/all-MiniLM-L6-v2`
-   **Output Dimensions**: **384**
-   **Reasoning**: This model provides an excellent balance of speed, size (~80MB), and quality for semantic similarity tasks. Its 384 dimensions are a perfect match for our database schema, where the `embedding` columns are defined as `VECTOR(384)`. The Apache 2.0 license also makes it ideal for commercial use.

---

## 3. Phase 1: Offline Batch Embedding

This is a one-time or periodic process that populates the `embedding` column for our core database tables. It is orchestrated by the `backend/scripts/generate_embeddings.py` script.

### Execution Flow

1.  **Load Model**: The script begins by loading the `all-MiniLM-L6-v2` model into memory.
2.  **Fetch Un-embedded Rows**: It makes `GET` requests to the Supabase REST API to fetch all rows from two key tables where the `embedding` column is `NULL`:
    *   `icd_codes`
    *   `snomed_concepts`
3.  **Generate Embeddings**: For each row, it generates a 384-dimension vector embedding.
    *   For `icd_codes`, the input text is a combination of the code and its description (e.g., `"E11.9 Type 2 diabetes mellitus without complications"`) to create a richer semantic representation.
    *   For `snomed_concepts`, the input text is simply the concept's description.
    *   The `normalize_embeddings=True` parameter is used, which is essential for accurate cosine similarity calculations in `pgvector`.
4.  **Update Database**: For each generated embedding, the script sends a `PATCH` request back to the Supabase API to update the specific row, filling in the `embedding` column.

This offline process ensures that runtime queries are fast, as the expensive work of embedding our entire knowledge base is done ahead of time.

---

## 4. Phase 2: Runtime Semantic Search

This phase occurs live within the `icd_embedding_node` when it's triggered by the LangGraph router.

### Execution Flow

1.  **Trigger**: The `_route_after_mapping` conditional edge directs the workflow to this node only if the `candidate_icd_codes` list is empty after the preceding mapping steps.
2.  **Lazy-Load Model**: The `icd_embedding_node` lazy-loads the `sentence-transformers` model. This is a critical optimization that ensures the ~80MB model is only loaded into memory if this fallback path is actually needed, keeping the primary workflow lightweight.
3.  **Generate Query Embedding**: It takes the `primary_text` from the `structured_entities` and generates a 384-dimension query vector on the fly using the same `all-MiniLM-L6-v2` model.
4.  **Execute RPC Search**: It calls a PostgreSQL stored procedure in our database named `match_icd_codes` via a Supabase `rpc` call.
    ```python
    # In backend/agents/icd_embedding.py
    candidates = await rpc(
        "match_icd_codes",
        {
            "query_embedding": _vector_to_pg_literal(embedding),
            "match_threshold": SIMILARITY_THRESHOLD, # e.g., 0.55
            "match_count": EMBEDDING_TOP_K,          # e.g., 5
        },
    )
    ```
5.  **Database-Side Logic (`match_icd_codes` function)**:
    *   The stored procedure takes the query embedding and performs a **cosine similarity** search against the `embedding` column of the `icd_codes` table.
    *   The `<=>` operator from `pgvector` is used to calculate the distance.
    *   It filters the results to only include codes where the similarity is above the `match_threshold` and returns the top `match_count` results.
6.  **Populate State**: The results from the RPC call are used to populate the `state.candidate_icd_codes` list. The `mapping_path` is set to `"embedding_fallback"` for auditability.

The workflow then proceeds to the `icd_decision_node`, which now has a list of semantically relevant candidates to score and rank.

import json
import asyncpg

model = SentenceTransformer("all-MiniLM-L6-v2")

async def icd_retrieval_node(state: CodingState) -> CodingState:
    """
    Retrieve top 5 ICD candidates using pgvector semantic similarity.
    Deterministic — no LLM involved.
    """
    diagnosis_text = state["structured_entities"]["diagnosis"]
    # Include comorbidities for richer embedding context
    comorbidities = " ".join(state["structured_entities"].get("comorbidities", []))
    query_text = f"{diagnosis_text} {comorbidities}".strip()

    # Generate query embedding
    query_embedding = model.encode(query_text, normalize_embeddings=True)
    embedding_json = json.dumps(query_embedding.tolist())

    # Query pgvector for top 5 semantically similar billable ICD codes
    results = await db.fetch(
        """
        SELECT
            code,
            description,
            is_cc,
            is_mcc,
            base_reimbursement,
            1 - (embedding <=> $1::vector) AS similarity_score
        FROM icd_codes
        WHERE is_billable = TRUE
          AND embedding IS NOT NULL
        ORDER BY embedding <=> $1::vector
        LIMIT 5;
        """,
        embedding_json
    )

    state["candidate_icd_codes"] = [
        {
            "code": row["code"],
            "description": row["description"],
            "is_cc": row["is_cc"],
            "is_mcc": row["is_mcc"],
            "base_reimbursement": float(row["base_reimbursement"]),
            "similarity_score": float(row["similarity_score"])
        }
        for row in results
    ]

    return state
```

---

## Supabase Setup Requirements

### 1. Enable pgvector Extension

In Supabase SQL Editor:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Or in Supabase dashboard: **Database → Extensions → vector → Enable**

### 2. Embedding Column on icd_codes

```sql
ALTER TABLE icd_codes 
ADD COLUMN IF NOT EXISTS embedding VECTOR(384);
```

### 3. Vector Index (Critical for Performance)

```sql
-- IVFFlat index for approximate nearest neighbor (fast at scale)
CREATE INDEX ON icd_codes 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

**What `lists = 100` means:**
The IVFFlat index divides vectors into 100 clusters. For 500 codes, `lists = 10–50` is fine. For 70,000 codes, `lists = 500` recommended.

---

## Similarity Score Interpretation

| Score Range | Interpretation |
|---|---|
| 0.95 – 1.00 | Very high confidence match |
| 0.85 – 0.94 | Strong match, likely correct |
| 0.70 – 0.84 | Moderate match, review recommended |
| < 0.70 | Weak match, flag for human review |

These thresholds feed into the confidence score returned by the API.

---

## Enriching the Query Embedding

Better embedding = better matching. Include more context in the query string:

```python
# Basic
query_text = diagnosis_text

# Better
query_text = f"{diagnosis_text}, severity: {severity}, comorbidities: {comorbidities}"

# Best (for production)
query_text = f"Clinical condition: {diagnosis_text}. Severity: {severity}. " \
             f"Comorbidities: {comorbidities}. Laterality: {laterality}."
```

More context in the query → more specific ICD match.

---

## Full Embedding Pipeline Diagram

```
ICD Database Seeding (One-Time Batch)
─────────────────────────────────────
icd_codes table rows
    │
    ▼
SentenceTransformer("all-MiniLM-L6-v2")
    │
    ▼
384-dim normalized embedding vector
    │
    ▼
Stored in icd_codes.embedding (VECTOR(384))
    │
    ▼
IVFFlat index created for cosine similarity



Runtime Retrieval (Per Request)
──────────────────────────────
Extracted diagnosis text
    │
    ▼
SentenceTransformer encodes on CPU
    │
    ▼
Query embedding (384-dim)
    │
    ▼
pgvector: embedding <=> query_embedding
(cosine distance, ascending order)
    │
    ▼
Top 5 ICD codes returned
    │
    ▼
Deterministic validation:
  ✓ is_billable = TRUE
  ✓ Similarity score > threshold
  ✓ Code in icd_codes master table
    │
    ▼
Passed to ICD Decision Agent
```

---

## Why This is Architecturally Correct

| Concern | How We Address It |
|---|---|
| LLM hallucination of codes | Embedding search uses only real DB codes |
| Rare conditions not in map | Semantic fallback finds closest match |
| Performance at 500 codes | IVFFlat index handles fast retrieval |
| Performance at 70,000 codes | Same index, adjust `lists` parameter |
| Model portability | Model abstracted, swappable without logic change |

---

## Dependencies

```txt
# requirements.txt additions
sentence-transformers==2.7.0
pgvector==0.3.2
asyncpg==0.29.0
```

---

## What to Say in Pitch

> *"We use sentence-transformer embeddings to convert clinical diagnosis text into 384-dimensional vectors stored in pgvector within Supabase. At runtime, the extracted diagnosis is embedded and compared against our ICD code vectors using cosine similarity. The top 5 candidates are then validated deterministically — ensuring only billable, version-correct ICD codes reach the decision agent."*
