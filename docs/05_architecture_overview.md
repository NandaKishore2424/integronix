# 05 — Architecture Overview

## Architecture Philosophy

- **LLM for reasoning only** — clinical parsing, severity detection
- **Deterministic engine for ICD code selection** — no hallucinations
- **Agentic orchestration** — LangGraph manages workflow state and branching
- **API-first design** — frontend is decoupled from all logic

---

## System Architecture Diagram (Text Representation)

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (Next.js)                        │
│   Upload PDF | Enter Human Code | View Dashboard & Audit        │
└─────────────────────────┬───────────────────────────────────────┘
                          │ REST API calls
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                   API Layer (FastAPI)                            │
│   /upload  /parse  /map  /audit  /risk                          │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│               LangGraph Agent Orchestration                      │
│                                                                  │
│  ┌────────────┐    ┌──────────────┐    ┌──────────────────┐    │
│  │ Doc Process │───▶│ Clinical     │───▶│ ICD Candidate    │    │
│  │   Node     │    │ Extraction   │    │ Retrieval Node   │    │
│  │(Det.)      │    │ Agent (LLM)  │    │ (Det. + pgvector)│    │
│  └────────────┘    └──────────────┘    └────────┬─────────┘    │
│                                                  │              │
│                                                  ▼              │
│                                        ┌──────────────────┐    │
│                                        │  ICD Decision    │    │
│                                        │  Agent (Hybrid)  │    │
│                                        └────────┬─────────┘    │
│                                                  │              │
│                              ┌───────────────────┤              │
│                              │ human_icd         │              │
│                              │ provided?         │              │
│                         Yes  ▼               No  ▼              │
│                    ┌──────────────┐    ┌──────────────────┐    │
│                    │    Audit     │    │   Risk Scoring   │    │
│                    │ Comparison   │───▶│   Node (Det.)    │    │
│                    │    Agent     │    └──────────────────┘    │
│                    └──────────────┘                            │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Data Layer                                     │
│                                                                  │
│   ┌──────────────────────┐    ┌──────────────────────────────┐  │
│   │     PostgreSQL        │    │        pgvector              │  │
│   │  icd_codes table      │    │   Semantic embeddings for    │  │
│   │  audit_log table      │    │   diagnosis fuzzy matching   │  │
│   │  revenue_lookup table │    └──────────────────────────────┘  │
│   └──────────────────────┘                                      │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│               External Services                                  │
│   Groq API (LLM inference) │ PDF Extractor Library              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Layer Breakdown

### 1. Presentation Layer (Next.js Frontend)
- PDF upload interface
- Human ICD code entry
- Dashboard: ICD suggestion, confidence, revenue delta, risk flag
- Audit comparison view

### 2. API Layer (FastAPI)
- `POST /upload` — Accept and process PDF
- `POST /parse` — Trigger clinical extraction
- `POST /map` — Run deterministic mapping
- `POST /audit` — Run audit comparison
- `GET /risk` — Retrieve risk score
- Each endpoint maps to a LangGraph workflow step

### 3. Agent Orchestration Layer (LangGraph)
- Stateful multi-agent graph
- Conditional edge routing (audit only if human code provided)
- Shared state object flows through all nodes
- See `06_langgraph_agent_design.md` for full design

### 4. Data Layer (PostgreSQL + pgvector)
- `icd_codes` — Master ICD-10 dataset (curated)
- `audit_log` — Each comparison session record
- `revenue_lookup` — Simulated reimbursement values per code
- `pgvector` extension — Enables semantic similarity search

### 5. External Services
- **Groq API** — LLM inference (fast, low-latency)
- **PDF extraction library** — pdfplumber or PyMuPDF

---

## Technology Choices & Justification

| Technology | Purpose | Why |
|---|---|---|
| FastAPI | API Layer | Async, fast, OpenAPI docs auto-generated, Pydantic native |
| LangGraph | Agent Orchestration | Graph-based, stateful, supports conditional branching |
| Groq | LLM Inference | Ultra-low latency, good for demo speed |
| PostgreSQL | Primary DB | Reliable, ACID-compliant for clinical data |
| pgvector | Semantic Search | Native vector similarity inside Postgres |
| Pydantic | Validation | Enforces structured output from LLM |
| Next.js | Frontend | Fast, React-based, good for dashboard UIs |
| Docker Compose | Deployment | Local + cloud portability |

---

## Security Considerations

| Concern | Approach |
|---|---|
| PHI (Protected Health Information) | Encrypt at rest; do not log raw clinical text in production |
| API Security | JWT-based authentication on all endpoints |
| LLM Output | Validated with Pydantic before any DB write |
| ICD Code Integrity | Only codes from internal DB accepted; LLM cannot inject codes |
| Audit Logging | All comparisons logged with timestamps for traceability |

> **Note:** For POC, a simplified auth layer is acceptable. Production would require full HIPAA compliance architecture.

---

## Scalability Discussion

For POC, single-server deployment is sufficient.

For production scale:
- FastAPI can be scaled horizontally behind a load balancer
- LangGraph workflows can be queued via Celery or Redis Queue
- PostgreSQL can be scaled with read replicas for reporting queries
- ICD database updates managed via versioned migration scripts

---

## Limitations (Be Honest in Pitch)

| Limitation | Explanation |
|---|---|
| Mini ICD dataset (~500 codes) | Not exhaustive; production needs full 70,000+ code set |
| Mock revenue values | Real DRG grouper not implemented |
| No full NCCI engine | Bundling rules not validated |
| No payer-specific rules | Payer contract logic is Phase 4 |
| LLM parsing accuracy | Depends on model capability and prompt quality |

---

## Future Roadmap (Mention in Pitch)

| Phase | Feature |
|---|---|
| Phase 1 (Current) | POC: Parse → Map → Audit → Revenue delta |
| Phase 2 | Full ICD-10 + CPT code set |
| Phase 3 | DRG grouper integration |
| Phase 4 | NCCI + payer rule engines |
| Phase 5 | Multi-tenant SaaS for hospital networks |
