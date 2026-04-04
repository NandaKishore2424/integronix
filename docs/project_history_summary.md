# Integronix Project History & Notable Points

*This document summarizes the legacy `sprints_and_progress` and `v1_product` folders that tracked the active development of Integronix Version 1.*

## Overview
Integronix V1 was developed through an organized 7-phase Sprint model spanning from foundational database setup to full Role-Based Access Control (RBAC) and Payer Integrations. The platform serves as an AI-driven, autonomous medical coding and Revenue Cycle Management (RCM) pipeline.

## Notable Architectural Decisions
1. **Semantic Search via `pgvector`:** Transitioned from basic wildcard text search to 384-dimensional mathematical vector embeddings storing 71,000+ ICD-10-CM codes.
2. **Standardized Communication Formats:** Internally, the platform communicates utilizing the modern **FHIR R4 JSON** claim structure. Externally, it exports the required CMS-compliant **ANSI X12 EDI 837** and **EDI 835** syntax.
3. **Payer Adjudication Engine:** Designed a dynamic rules engine linking Hospitals and Insurance Payers within the same platform, utilizing Supabase RLS policies and `organization_id` keys to securely segregate data.

## Historical Sprint Breakdown
- **Sprint 1 & 2:** Database Foundation, Coding NLP Pipeline, ICD/CPT mappings, and Dynamic DRG financial computations.
- **Sprint 3 & 4:** Payer Integration, Supabase Auth setup, Frontend Architecture (Next.js App Router).
- **Sprint 5:** Trust & Automation (Compliance engine, Risk calculation).
- **Sprint 6:** Appeals and EDI 837/835 exporting logic.
- **Sprint 7:** Authentication, Multi-tenant RBAC (Role-Based Access Control), identifying edge bugs across Payer and Coder routing.

## Final Note
The extensive documentation folders regarding daily ticket plans, individual PRs, and day-to-day bug tracking logs have been deprecated and deleted as of the completion of Version 1 to maintain repository cleanliness. The `engineering_roadmap.md` goals from the initial V1 product phase have been successfully closed out.
