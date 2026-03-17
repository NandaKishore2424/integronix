# 01 — Project Overview

## Project Name
**Integronix — Revenue Integrity Engine**
*(Internal codename: CodePerfect)*

---

## Problem Statement

Hospitals and healthcare providers lose billions annually due to:

- **Under-coding** — Using non-specific ICD codes, missing CC/MCC capture
- **Over-coding** — Risk of audit, payer clawback, compliance violations
- **Manual coding inefficiency** — Human coders miss specificity, are slow, and inconsistent
- **No real-time audit layer** — Discrepancies between AI suggestion and human assignments go undetected
- **Revenue leakage** — Incorrect DRG grouping leads to reimbursement shortfall

Currently, hospitals rely on human medical coders who:
- Are expensive to hire and train
- Make specificity errors under time pressure
- Cannot process large case volumes consistently

---

## What We Are Building

**Integronix** is a **Revenue Integrity Engine** powered by Agentic AI.

It is NOT a chatbot.
It is NOT a code generation tool.
It is a **deterministic + agentic pipeline** that:

1. Parses clinical documents (PDFs / discharge summaries)
2. Extracts diagnosis, severity, and comorbidities using LLM
3. Maps them to exact ICD-10 codes from an internal validated database
4. Compares AI suggestion against human-coded input
5. Shows discrepancy, supporting evidence, and revenue impact
6. Assigns a compliance risk score

---

## Why This is Different

| Feature | Generic AI Tools | Integronix |
|---|---|---|
| ICD Code Generation | LLM generates (hallucination risk) | DB-backed deterministic lookup only |
| Audit Capability | None | Full human vs AI comparison |
| Revenue Intelligence | None | Simulated delta with CC/MCC flags |
| Explainability | Black box | Evidence text linked to each code |
| Compliance | Not addressed | Billable validation + risk scoring |

---

## Hackathon Context

- **Event:** Virtusa Jatayu Hackathon — Stage 2
- **Theme:** Agentic AI
- **Scale:** 20 teams competing, top 4 qualify
- **Target:** Finish **#1**
- **Format:** 20-minute pitch + 10-minute Q&A

---

## Positioning Statement

> *"Integronix demonstrates deterministic ICD mapping with agentic parsing and audit comparison. Full DRG grouping, NCCI rules, and payer-specific engines are part of our Phase 4 expansion roadmap."*

This statement is used during the pitch to show maturity and scope awareness.

---

## Technology Stack

| Layer | Technology |
|---|---|
| API Backend | FastAPI (Python) |
| Agent Orchestration | LangGraph |
| LLM Inference | Groq API |
| Database | PostgreSQL + pgvector |
| Frontend | Next.js |
| Schema Validation | Pydantic (backend), Zod (frontend) |
| Deployment | Docker Compose |

---

## Solo Execution Notes

- This is a **solo build**
- All backend, frontend, DB, and agent design is owned by one person
- Documentation is maintained here to preserve context across sessions
- Scope is deliberately kept minimal and sharp to ensure demo stability
