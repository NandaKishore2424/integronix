# 20 — Build Progress Log

> **Live tracking document.** Updated as each phase is completed.
> This is the single source of truth for "what's done vs what's next."

---

## ✅ Phase 0: Architecture & Documentation
**Status: COMPLETE**

All 19 reference docs written to `/docs`:
- Project overview, scope, strategy, Q&A prep
- Full system architecture, LangGraph agent design
- FHIR JSON schemas, SNOMED-ICD mapping strategy
- Embedding pipeline design, deterministic ICD algorithm
- Supabase SQL schema, step-by-step build guide

---

## ✅ Phase 1: Project Scaffolding
**Status: COMPLETE**

### Backend (`/backend`)
| File | Status |
|---|---|
| `main.py` | ✅ Created |
| `database.py` | ✅ Created — asyncpg pool, Supabase SSL |
| `models.py` | ✅ Created — Pydantic schemas |
| `routes/health.py` | ✅ Created — `GET /health` |
| `routes/icd.py` | ✅ Created — `GET /icd/{code}`, `GET /icd/snomed/{code}/mappings` |
| `services/icd_service.py` | ✅ Created — DB queries |
| `agents/graph.py` | ✅ Stub — CodingState defined |
| `requirements.txt` | ✅ Created |
| `.env.example` | ✅ Created |
| `Dockerfile` | ✅ Created |

### Frontend (`/frontend`)
| File | Status |
|---|---|
| Next.js TypeScript app | ✅ Scaffolded via `create-next-app` |
| `.env.example` | ✅ Created |

### Root
| File | Status |
|---|---|
| `docker-compose.yml` | ✅ Created |
| `.gitignore` | ✅ Created |

### Next Steps for Phase 1 Completion
- [ ] **YOU:** Copy `backend/.env.example` → `backend/.env` and fill in Supabase credentials
- [ ] **YOU:** Copy `frontend/.env.example` → `frontend/.env.local` and fill in Supabase URL + anon key
- [ ] **VERIFY:** `cd backend && pip install -r requirements.txt && uvicorn main:app --reload`
      → Should start on port 8000 (DB error is expected until schema is run)
- [ ] **VERIFY:** `cd frontend && npm run dev`
      → Should start on port 3000

---

## ⬜ Phase 2: Supabase Schema + DB Connection
**Status: NOT STARTED**

### Steps
1. Run full SQL from `16_supabase_schema_full.md` in Supabase SQL Editor
2. Seed 10 ICD codes, 5 SNOMED concepts, 6 mappings (Steps 8–10)
3. Run 3 verification queries
4. Test `GET /health` → should return `icd_codes_loaded: 10`
5. Test `GET /api/v1/icd/E11.22` → should return full ICD record

---

## ⬜ Phase 3: Clinical Extraction Endpoint
**Status: NOT STARTED**

- `POST /api/v1/upload` — PDF upload + text extraction
- `POST /api/v1/parse` — Groq LLM call + Pydantic validation
- Return structured `ExtractionResult` JSON

---

## ⬜ Phase 4: LangGraph Agents
**Status: NOT STARTED**

Wire all 8 nodes from `17_langgraph_snomed_nodes.md`:
1. Document Processing
2. Clinical Extraction
3. SNOMED Resolver
4. SNOMED→ICD Mapper
5. ICD Embedding Fallback
6. ICD Decision (deterministic algorithm from `18_deterministic_icd_algorithm.md`)
7. Audit Comparison
8. Risk Scoring

---

## ⬜ Phase 5: Frontend Dashboard
**Status: NOT STARTED**

- Upload component
- Results dashboard (ICD code, confidence, revenue delta, risk)
- Audit comparison panel

---

## ⬜ Phase 6: Demo Prep
**Status: NOT STARTED**

- Run full 7-step demo flow 10 times without errors
- Prepare architecture slides
- Practice pitch + Q&A (`10_qa_preparation.md`)
