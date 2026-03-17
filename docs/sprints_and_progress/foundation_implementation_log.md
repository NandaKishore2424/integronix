# 19 — Foundation Implementation: Step-by-Step Execution Guide

> **Your current mission: Stabilize the database and backend before touching any agents.**
> Complete each checkpoint fully before moving to the next.
> Do not proceed if anything at the current checkpoint is broken.

---

## 🛑 Checkpoint 0 — Confirm Architecture Understanding

Before any code:

- [ ] You have read `16_supabase_schema_full.md` — understand all 6 tables
- [ ] You have read `17_langgraph_snomed_nodes.md` — understand the 8-node flow
- [ ] You have read `18_deterministic_icd_algorithm.md` — understand the decision engine
- [ ] You know: **LLM = parsing only. ICD codes = DB only. No exceptions.**

---

## ✅ CHECKPOINT 1 — Supabase Database

Goal: All tables exist, foreign keys work, seed data is queryable.

### Step 1.1 — Enable Extensions
Go to **Supabase → SQL Editor** and run:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

OR: Go to **Database → Extensions → Search "vector" → Enable**

### Step 1.2 — Create All Tables
Copy and run in order from `16_supabase_schema_full.md`:
1. `icd_codes` table
2. `snomed_concepts` table
3. `snomed_icd_map` table
4. `clinical_cases` table
5. `coding_results` table
6. `revenue_lookup` table

### Step 1.3 — Create All Indexes
Run all `CREATE INDEX` statements from Step 7 of `16_supabase_schema_full.md`.

### Step 1.4 — Insert Seed Data
Run Steps 8, 9, 10 from `16_supabase_schema_full.md`:
- 10 ICD codes
- 5 SNOMED concepts
- 6 SNOMED → ICD mappings

### Step 1.5 — Verify with Queries

Run the 3 verification queries at the bottom of `16_supabase_schema_full.md`.

**You must see:**
- 10 ICD rows ✅
- 5 SNOMED rows ✅
- 6 mapping rows with joined descriptions ✅

**🔴 DO NOT PROCEED if any verification fails. Fix schema first.**

---

## ✅ CHECKPOINT 2 — Backend Skeleton

Goal: FastAPI running. DB connection working. One query tested.

### Step 2.1 — Create Folder Structure

```bash
mkdir -p integronix/backend/{routes,services,agents,models}
touch integronix/backend/main.py
touch integronix/backend/database.py
touch integronix/backend/models.py
```

### Step 2.2 — Install Dependencies

```bash
pip install fastapi uvicorn asyncpg pydantic python-dotenv
```

Create `backend/requirements.txt`:
```
fastapi==0.111.0
uvicorn==0.30.0
asyncpg==0.29.0
pydantic==2.7.0
python-dotenv==1.0.0
sentence-transformers==2.7.0
langchain==0.2.0
langgraph==0.1.0
langchain-groq==0.1.0
pdfplumber==0.11.0
```

### Step 2.3 — Environment File

Create `backend/.env`:
```
SUPABASE_HOST=your-project.supabase.co
SUPABASE_DB=postgres
SUPABASE_USER=postgres
SUPABASE_PASSWORD=your-password
SUPABASE_PORT=5432
GROQ_API_KEY=your-groq-key
```

### Step 2.4 — Database Connection

Create `backend/database.py`:
```python
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

_pool = None

async def get_db_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            host=os.getenv("SUPABASE_HOST"),
            database=os.getenv("SUPABASE_DB"),
            user=os.getenv("SUPABASE_USER"),
            password=os.getenv("SUPABASE_PASSWORD"),
            port=int(os.getenv("SUPABASE_PORT", 5432)),
            ssl="require"
        )
    return _pool

async def close_db_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
```

### Step 2.5 — FastAPI App

Create `backend/main.py`:
```python
from fastapi import FastAPI
from contextlib import asynccontextmanager
from database import get_db_pool, close_db_pool

@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_db_pool()
    yield
    await close_db_pool()

app = FastAPI(
    title="Integronix API",
    description="Revenue Integrity Engine — Agentic ICD-10 Coding",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/health")
async def health():
    db = await get_db_pool()
    result = await db.fetchval("SELECT COUNT(*) FROM icd_codes")
    return {
        "status": "running",
        "icd_codes_loaded": result
    }
```

### Step 2.6 — Run and Test

```bash
cd backend
uvicorn main:app --reload --port 8000
```

Open browser → `http://localhost:8000/health`

**You must see:**
```json
{ "status": "running", "icd_codes_loaded": 10 }
```

**🔴 DO NOT PROCEED if this fails. Fix DB connection first.**

---

## ✅ CHECKPOINT 3 — ICD Retrieval Endpoint

Goal: `GET /icd/{code}` returns correct ICD details.

### Step 3.1 — ICD Service

Create `backend/services/icd_service.py`:
```python
from database import get_db_pool

async def get_icd_by_code(code: str) -> dict | None:
    db = await get_db_pool()
    row = await db.fetchrow(
        """
        SELECT code, description, chapter, category,
               is_billable, is_cc, is_mcc, base_reimbursement
        FROM icd_codes
        WHERE code = $1
        """,
        code
    )
    if not row:
        return None
    return dict(row)

async def get_snomed_mapping(snomed_code: str) -> list:
    db = await get_db_pool()
    rows = await db.fetch(
        """
        SELECT sim.icd_code, sim.mapping_type, sim.confidence,
               ic.description, ic.is_cc, ic.base_reimbursement
        FROM snomed_icd_map sim
        JOIN icd_codes ic ON ic.code = sim.icd_code
        WHERE sim.snomed_code = $1
        ORDER BY sim.confidence DESC
        """,
        snomed_code
    )
    return [dict(r) for r in rows]
```

### Step 3.2 — ICD Route

Create `backend/routes/icd.py`:
```python
from fastapi import APIRouter, HTTPException
from services.icd_service import get_icd_by_code, get_snomed_mapping

router = APIRouter(prefix="/icd", tags=["ICD"])

@router.get("/{code}")
async def fetch_icd(code: str):
    result = await get_icd_by_code(code.upper())
    if not result:
        raise HTTPException(status_code=404, detail=f"ICD code '{code}' not found")
    return result

@router.get("/snomed/{snomed_code}/mappings")
async def fetch_snomed_mappings(snomed_code: str):
    results = await get_snomed_mapping(snomed_code)
    if not results:
        raise HTTPException(status_code=404, detail=f"No ICD mappings for SNOMED '{snomed_code}'")
    return {"snomed_code": snomed_code, "mappings": results}
```

### Step 3.3 — Register in main.py

Add to `main.py`:
```python
from routes.icd import router as icd_router
app.include_router(icd_router, prefix="/api/v1")
```

### Step 3.4 — Test

```
GET http://localhost:8000/api/v1/icd/E11.22
GET http://localhost:8000/api/v1/icd/snomed/44054006/mappings
```

**You must see:**
- Full ICD record for E11.22 ✅
- 3 ICD mappings for SNOMED 44054006 ✅

Also test FastAPI docs: `http://localhost:8000/docs`

**🔴 DO NOT PROCEED if queries return incorrect data.**

---

## ✅ CHECKPOINT 4 — Embeddings (Basic Test)

Goal: Confirm `sentence-transformers` works locally before embedding the full DB.

### Step 4.1 — Quick Test Script

Create `backend/test_embedding.py`:
```python
from sentence_transformers import SentenceTransformer
import json

model = SentenceTransformer("all-MiniLM-L6-v2")

text = "Type 2 diabetes mellitus with chronic kidney disease stage 3"
embedding = model.encode(text, normalize_embeddings=True)

print(f"Embedding dimension: {len(embedding)}")   # Should be 384
print(f"First 5 values: {embedding[:5].tolist()}")
print("Embedding test passed ✅")
```

```bash
python test_embedding.py
```

**You must see `Embedding dimension: 384` ✅**

### Step 4.2 — Generate Embeddings for Seeded ICD Codes

Run `db/generate_embeddings.py` (from `15_embedding_pipeline.md`).

Update the 10 seeded ICD codes with their embeddings.

Verify in Supabase:
```sql
SELECT code, description,
       CASE WHEN embedding IS NULL THEN 'MISSING' ELSE 'PRESENT' END AS has_embedding
FROM icd_codes;
```

All 10 rows should show `PRESENT`.

---

## 🛑 STOP HERE — Summary Before Phase 2

After completing all 4 checkpoints, you should have:

| Item | Status |
|---|---|
| Supabase: 6 tables created | ✅ |
| Supabase: 10 ICD + 5 SNOMED + 6 mappings seeded | ✅ |
| FastAPI: `/health` returns DB count | ✅ |
| FastAPI: `/icd/{code}` returns correct record | ✅ |
| FastAPI: SNOMED mappings endpoint working | ✅ |
| Embeddings: 384-dim model working locally | ✅ |
| ICD embeddings: Stored in Supabase pgvector | ✅ |

**When all these are ✅ → Report back. We move to Phase 2: Clinical Extraction Endpoint.**

---

## 📌 Phase 2 Preview (Do NOT start yet)

Once foundation is stable, Phase 2 will be:

1. `POST /upload` — Accept PDF, extract text
2. `POST /parse` — Single LLM call, return structured JSON
3. Validate output with Pydantic `ExtractionResult`
4. Test with a real clinical PDF

Still no LangGraph. Still no SNOMED mapping. One clean parsing function.

---

## Common Errors & Fixes

| Error | Likely Cause | Fix |
|---|---|---|
| `ssl connection refused` | Wrong Supabase host | Check `.env` — use full host with port 5432 |
| `undefined table` | Wrong table order | Create `icd_codes` before `snomed_icd_map` |
| `vector extension not found` | Extension not enabled | Enable in Supabase dashboard |
| `Foreign key violation` | Seed order wrong | Seed `icd_codes` before `snomed_icd_map` |
| `384 dim mismatch` | Wrong model | Confirm using `all-MiniLM-L6-v2` exactly |
| `asyncpg cannot connect` | Pool not initialized | Check lifespan function in `main.py` |
