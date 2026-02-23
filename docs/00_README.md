# 📁 Integronix — Project Documentation Index
## Virtusa Jatayu Hackathon | Stage 2

> **Application Name:** Integronix
> **Theme:** Agentic AI
> **Goal:** Finish #1 among 20 teams in Stage 2

---

## 📂 Documentation Structure

### 🎯 Strategy & Planning
| File | Description |
|------|-------------|
| [`01_project_overview.md`](./01_project_overview.md) | What we're building, goals, strategic positioning |
| [`02_stage2_requirements.md`](./02_stage2_requirements.md) | Stage 2 deliverables and evaluation criteria |
| [`03_winning_strategy.md`](./03_winning_strategy.md) | Strategy to finish #1, competitive differentiation |
| [`04_scope_and_features.md`](./04_scope_and_features.md) | POC feature scope — what's in and what's out |
| [`09_sprint_plan.md`](./09_sprint_plan.md) | 4-week sprint plan with milestones and folder structure |
| [`10_qa_preparation.md`](./10_qa_preparation.md) | Pre-written answers for all hard Q&A questions |

### 🏗 Architecture & Design
| File | Description |
|------|-------------|
| [`05_architecture_overview.md`](./05_architecture_overview.md) | Full system architecture with diagrams, tech stack, security |
| [`06_langgraph_agent_design.md`](./06_langgraph_agent_design.md) | LangGraph node definitions, state, routing, code stubs |
| [`11_langgraph_explainer.md`](./11_langgraph_explainer.md) | What LangGraph is, why we use it, mental model |

### 🏥 Healthcare Data Standards
| File | Description |
|------|-------------|
| [`12_coding_systems_reference.md`](./12_coding_systems_reference.md) | ICD-10, SNOMED, LOINC, CPT — what they are and how they relate |
| [`13_fhir_json_schema.md`](./13_fhir_json_schema.md) | FHIR-aligned JSON schemas for Condition, Claim, Observation, Audit |
| [`14_snomed_icd_mapping.md`](./14_snomed_icd_mapping.md) | 3-layer SNOMED → ICD mapping strategy with SQL schema and code |
| [`15_embedding_pipeline.md`](./15_embedding_pipeline.md) | pgvector embedding pipeline — batch generation + runtime search |

### 🗄 Data & API
| File | Description |
|------|-------------|
| [`07_database_schema.md`](./07_database_schema.md) | Original DB schema (reference) |
| [`08_api_design.md`](./08_api_design.md) | All FastAPI endpoints with request/response schemas |
| [`16_supabase_schema_full.md`](./16_supabase_schema_full.md) | **Complete Supabase SQL** — all 6 tables, indexes, seed data, verification queries |

### 🔧 Implementation
| File | Description |
|------|-------------|
| [`17_langgraph_snomed_nodes.md`](./17_langgraph_snomed_nodes.md) | **SNOMED-aware LangGraph** — all 8 nodes with Python code stubs |
| [`18_deterministic_icd_algorithm.md`](./18_deterministic_icd_algorithm.md) | **7-step ICD decision algorithm** — full Python implementation |
| [`19_foundation_implementation.md`](./19_foundation_implementation.md) | **Step-by-step build guide** — 4 checkpoints before touching agents |

---

## 🧭 Quick Context

- **Solo build** — all backend, DB, agents, and frontend owned by one person
- Docs are kept here so full context survives between work sessions
- Agent mode uses these docs to build correctly

## Tech Stack

| Layer | Technology |
|---|---|
| API Backend | FastAPI (Python) |
| Agent Orchestration | LangGraph |
| LLM Inference | Groq API |
| Database | Supabase (PostgreSQL + pgvector) |
| Frontend | Next.js |
| Schema Validation | Pydantic / Zod |
| Medical Standards | ICD-10-CM, SNOMED CT, LOINC, CPT |
| Data Format | FHIR-aligned JSON |

**Last Updated:** February 2026
