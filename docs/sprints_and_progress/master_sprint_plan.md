# 09 — 4-Week Sprint Plan

## Context

- Solo execution
- ~4 weeks build time
- Goal: Stable, demo-ready POC by Week 4
- Weekly mentor connects require showing measurable progress

---

## Week 1 — Foundation & Data Layer

**Goal:** Working skeleton + ICD database ready

### Tasks

| # | Task | Status |
|---|---|---|
| 1 | Set up project folder structure (`/frontend`, `/backend`, `/db`) | [ ] |
| 2 | Initialize FastAPI app with health check endpoint | [ ] |
| 3 | Initialize Next.js frontend app (basic layout) | [ ] |
| 4 | Set up PostgreSQL + pgvector locally via Docker | [ ] |
| 5 | Write and run `icd_codes` schema migration | [ ] |
| 6 | Curate and seed ~300–500 ICD codes into DB (with categories) | [ ] |
| 7 | Generate and store embeddings for all seeded codes | [ ] |
| 8 | Set up Docker Compose for full stack local run | [ ] |

### Milestone: "Data foundation is rock solid. ICD DB is seeded and searchable."

### Mentor Connect Talking Points:
- ICD database schema designed and seeded
- pgvector similarity search working
- FastAPI skeleton running

---

## Week 2 — Core Backend Pipeline

**Goal:** Full parse → map pipeline working end-to-end

### Tasks

| # | Task | Status |
|---|---|---|
| 1 | Implement `doc_processing_node` (PDF text extraction) | [ ] |
| 2 | Design and test LLM prompt for clinical extraction | [ ] |
| 3 | Implement `clinical_extraction_agent` (Groq + Pydantic) | [ ] |
| 4 | Implement `icd_retrieval_node` (pgvector similarity search) | [ ] |
| 5 | Implement `icd_decision_agent` (hybrid reasoning + validation) | [ ] |
| 6 | Wire up LangGraph graph with these 4 nodes | [ ] |
| 7 | Add `POST /upload` and `POST /map` API endpoints | [ ] |
| 8 | Test full pipeline with 3–5 sample clinical documents | [ ] |

### Milestone: "Upload PDF → get ICD code suggestion. Deterministic. No hallucinations."

### Mentor Connect Talking Points:
- Full parse-to-map pipeline working
- LangGraph graph executing correctly
- Tested with real clinical text samples
- Groq integration stable

---

## Week 3 — Audit Layer + Revenue Simulation

**Goal:** Audit comparison + revenue delta working

### Tasks

| # | Task | Status |
|---|---|---|
| 1 | Implement `audit_comparison_agent` node | [ ] |
| 2 | Seed `revenue_lookup` table with simulated values | [ ] |
| 3 | Implement `risk_scoring_node` | [ ] |
| 4 | Add conditional routing in LangGraph (audit branch) | [ ] |
| 5 | Add `POST /audit` and `GET /result` API endpoints | [ ] |
| 6 | Write `audit_log` table insert logic | [ ] |
| 7 | Test audit comparison with 5 scenarios (match, mismatch, unsupported) | [ ] |

### Milestone: "Input human ICD code → see discrepancy + evidence + $ delta."

### Mentor Connect Talking Points:
- Audit comparison mode fully working
- Revenue simulation numbers visible
- Risk scoring logic explained
- Multiple audit scenarios tested and stable

---

## Week 4 — Frontend, Polish, Demo Prep

**Goal:** UI ready + full demo flow stable

### Tasks

| # | Task | Status |
|---|---|---|
| 1 | Build PDF upload UI in Next.js | [ ] |
| 2 | Build dashboard: ICD result, confidence, risk flag | [ ] |
| 3 | Build audit panel: human code input + discrepancy display | [ ] |
| 4 | Connect frontend to all API endpoints | [ ] |
| 5 | Run full end-to-end demo flow 10 times without errors | [ ] |
| 6 | Prepare architecture document (align with template) | [ ] |
| 7 | Prepare PPT slides | [ ] |
| 8 | Practice 20-minute pitch | [ ] |
| 9 | Prepare Q&A answers (see `10_qa_preparation.md`) | [ ] |

### Milestone: "Full 7-step demo flow runs without any errors. Pitch is rehearsed."

---

## Priority Rules (Execution Discipline)

1. **Core pipeline first.** If Week 2 falls behind, cut UI polish from Week 4.
2. **Never break working demos.** Branch all unstable work.
3. **One working scenario** is better than five broken ones.
4. **Data seeds first.** A good DB > a good UI.

---

## Folder Structure

```
integronix/
├── docs/                    ← You are here
├── backend/
│   ├── main.py
│   ├── routers/
│   │   ├── upload.py
│   │   ├── parse.py
│   │   ├── map.py
│   │   ├── audit.py
│   │   └── result.py
│   ├── agents/
│   │   ├── graph.py         ← LangGraph definition
│   │   ├── doc_processor.py
│   │   ├── clinical_extractor.py
│   │   ├── icd_retrieval.py
│   │   ├── icd_decision.py
│   │   ├── audit_agent.py
│   │   └── risk_scorer.py
│   ├── models/              ← Pydantic schemas
│   ├── db/
│   │   ├── connection.py
│   │   └── queries.py
│   └── requirements.txt
├── frontend/
│   ├── pages/
│   ├── components/
│   └── package.json
├── db/
│   ├── migrations/
│   ├── seed_icd_codes.py
│   └── generate_embeddings.py
└── docker-compose.yml
```
