# 15 — Embedding Pipeline for ICD Similarity Search

## Purpose

When SNOMED direct mapping fails, we use **semantic embedding similarity** to find the best matching ICD-10 codes from our internal database.

This is powered by **pgvector** inside Supabase/PostgreSQL.

---

## Embedding Model Choice

### Recommended: `sentence-transformers/all-MiniLM-L6-v2`

| Property | Value |
|---|---|
| Output dimensions | 384 |
| Size | ~80MB |
| Speed | Fast (CPU-friendly) |
| Quality | Strong for medical text |
| License | Apache 2.0 (free) |

**Why 384 dimensions?**
Our Supabase `icd_codes.embedding` column is defined as `VECTOR(384)` — an exact match.

**Alternative:** OpenAI `text-embedding-ada-002` (1536 dims) — higher quality, costs money, requires updating column to `VECTOR(1536)`.

For POC: Use MiniLM (free, fast, no API cost).
For production: Evaluate OpenAI or a medical-domain fine-tuned model.

---

## Phase 1: Offline Batch — Generate and Store ICD Embeddings

This runs **once** when the ICD database is seeded. Run it again when new codes are added.

### Script: `db/generate_embeddings.py`

```python
from sentence_transformers import SentenceTransformer
import psycopg2
import json

# Load model
model = SentenceTransformer("all-MiniLM-L6-v2")

# Connect to Supabase/PostgreSQL
conn = psycopg2.connect(
    host="your-supabase-host",
    dbname="postgres",
    user="postgres",
    password="your-password",
    port=5432
)
cur = conn.cursor()

# Fetch all ICD codes without embeddings
cur.execute("SELECT code, description FROM icd_codes WHERE embedding IS NULL")
rows = cur.fetchall()

print(f"Generating embeddings for {len(rows)} ICD codes...")

batch_size = 64
for i in range(0, len(rows), batch_size):
    batch = rows[i:i + batch_size]
    codes = [row[0] for row in batch]
    descriptions = [row[1] for row in batch]

    # Generate embeddings for the batch
    embeddings = model.encode(descriptions, normalize_embeddings=True)

    # Update the DB
    for code, embedding in zip(codes, embeddings):
        cur.execute(
            "UPDATE icd_codes SET embedding = %s WHERE code = %s",
            (json.dumps(embedding.tolist()), code)
        )

conn.commit()
cur.close()
conn.close()

print("Done. All ICD embeddings stored.")
```

**What "normalize_embeddings=True" does:**
Normalizes to unit length — required for correct cosine similarity calculations.

---

## Phase 2: Runtime — Query at Request Time

When the Clinical Extraction Agent produces a diagnosis string at runtime, we:
1. Generate its embedding on the fly
2. Query pgvector for the most similar ICD codes

### In FastAPI + LangGraph ICD Retrieval Node

```python
from sentence_transformers import SentenceTransformer
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
