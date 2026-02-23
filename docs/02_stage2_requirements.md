# 02 — Stage 2 Requirements

## What Stage 2 Demands

Stage 2 of the Virtusa Jatayu Hackathon requires the following deliverables:

| Deliverable | Description |
|---|---|
| **Architecture Document** | System diagram, data flow, tech choices, security, scalability, limitations, and roadmap |
| **PPT Presentation** | Clear slides covering problem, solution, architecture, demo, business impact |
| **Working Model / POC Demo** | A functional prototype that demonstrates the core pipeline |
| **Documented Code** | Clean, readable, and commented codebase |

> ⚠️ **Not just slides. Not just diagrams. A functional prototype is required.**

---

## Architecture Document — What They Expect

The architecture document must include:

- [ ] System architecture diagram
- [ ] Data flow explanation (step-by-step)
- [ ] Technology choices with justification
- [ ] Security considerations (PHI, HIPAA alignment)
- [ ] Scalability discussion
- [ ] Limitations acknowledged
- [ ] Future scope / roadmap

Must show details like:
- API layer design
- Database schema
- Agent workflow
- Deployment strategy

---

## Evaluation Criteria

Judges will score based on:

1. **Clarity of Architecture** — Is the system well-designed and explainable?
2. **Feasibility** — Can this actually be built and extended?
3. **Working Demo** — Does the prototype function correctly?
4. **Technical Depth** — Do you understand what you've built?
5. **Alignment with Business Need** — Is this solving a real problem?

---

## Logistics

- **20 teams in Stage 2** — Only **top 4 per Business Unit** qualify
- **Weekly Mentor Connects** — Progress check-ins during build period
- **Final Evaluation:** 20-minute pitch + 10-minute Q&A
- Architecture template will be provided (align formatting when received; content is already being prepared)

---

## Our Advantage (Pre-Onboarding)

We are starting before the architecture template is even given.

By the time of the first mentor connect, we will have:
- [x] ICD database schema designed
- [ ] Parsing pipeline in progress
- [ ] Deterministic mapping logic defined
- [ ] Audit comparison logic designed
- [ ] API-first architecture scaffolded

This gives us a **head start** over teams still brainstorming.

---

## Notes on Demo Stability

The demo must be **bulletproof**. The demo flow is:

```
Upload document
  → Extract diagnosis
  → Map to ICD-10 (internal DB)
  → Compare with human-coded input
  → Show discrepancy
  → Show evidence text
  → Show revenue delta
```

No bugs. No confusion. No delays during demo.
