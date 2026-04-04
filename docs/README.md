# Integronix Documentation

Welcome to the central documentation hub for **Integronix** — the Agentic AI-powered Revenue Integrity Engine built for the Virtusa Jatayu Hackathon.

To make navigation simple and intuitive, our documentation is structured into five logical domains:

## 🎯 1. Product & Strategy
*For leadership, PMs, and judges to understand the "Why" and the "What."*
* [`master_project_documentation.md`](./product_and_strategy/master_project_documentation.md) — Comprehensive master documentation.
* [`introduction.md`](./product_and_strategy/introduction.md) — High-level introduction to the system.
* [`goals_and_constraints.txt`](./product_and_strategy/goals_and_constraints.txt) — Business goals and technical constraints.
* [`productization_assessment.txt`](./product_and_strategy/productization_assessment.txt) — Assessment for production readiness.
* [`project_overview.md`](./product_and_strategy/project_overview.md) — The core problem statement and solution.
* [`stage2_requirements.md`](./product_and_strategy/stage2_requirements.md) — Hackathon deliverables.
* [`winning_strategy.md`](./product_and_strategy/winning_strategy.md) — How we win.
* [`scope_and_features.md`](./product_and_strategy/scope_and_features.md) — What is built and what isn't.
* [`qa_preparation.md`](./product_and_strategy/qa_preparation.md) — Anticipated questions and answers.
* [`real_world_failures_and_cases.md`](./product_and_strategy/real_world_failures_and_cases.md) — Massive hospital coding failures we prevent.
* [`hospital_rcm_workflow.md`](./product_and_strategy/hospital_rcm_workflow.md) — End-to-end hospital billing workflow.
* [`rcm_user_journey.md`](./product_and_strategy/rcm_user_journey.md) — User journey mapping for Revenue Cycle Management.

## 🏗️ 2. Architecture & Backend
*Core engineering documentation for how the LangGraph, AI, and APIs work.*
* [`architecture_overview.md`](./architecture_and_backend/architecture_overview.md) — System boundaries and stack.
* [`Integronix_Architecture_Document.md`](./architecture_and_backend/Integronix_Architecture_Document.md) — Comprehensive architecture specification.
* [`system_architecture.md`](./architecture_and_backend/system_architecture.md) — Core system architecture breakdown.
* [`data_flow_and_security.md`](./architecture_and_backend/data_flow_and_security.md) — Data flow diagrams and security models.
* [`tech_stack_and_conclusion.md`](./architecture_and_backend/tech_stack_and_conclusion.md) — Technology choices and final thoughts.
* [`langgraph_agent_design.md`](./architecture_and_backend/langgraph_agent_design.md) — Base node logic.
* [`api_design_and_endpoints.md`](./architecture_and_backend/api_design_and_endpoints.md) — FastAPI routes and schemas.
* [`langgraph_explainer.md`](./architecture_and_backend/langgraph_explainer.md) — Why LangGraph over LangChain.
* [`vector_embedding_pipeline.md`](./architecture_and_backend/vector_embedding_pipeline.md) — pgvector and sentence-transformers.
* [`langgraph_snomed_flow.md`](./architecture_and_backend/langgraph_snomed_flow.md) — The new WHO/SNOMED extraction pipeline.
* [`deterministic_icd_decision_algorithm.md`](./architecture_and_backend/deterministic_icd_decision_algorithm.md) — The 7-step code ranker.

## 🗄️ 3. Database & Schemas
*Everything related to Supabase, Postgres models, and FHIR standards.*
* [`initial_database_schema.md`](./database_and_schemas/initial_database_schema.md) — The V1 basics.
* [`fhir_json_schema.md`](./database_and_schemas/fhir_json_schema.md) — Interoperability specs.
* [`supabase_schema_full.md`](./database_and_schemas/supabase_schema_full.md) — Full SQL structure.
* [`database_schema_explained_simply.md`](./database_and_schemas/database_schema_explained_simply.md) — A layman's guide to the tables.
* [`auth_roles_and_tenant_setup.md`](./database_and_schemas/auth_roles_and_tenant_setup.md) — Multi-tenancy and JWT RBAC logic.

## ⚕️ 4. Medical Domain Knowledge
*Healthcare data sources and terminology logic.*
* [`medical_coding_systems_reference.md`](./medical_domain_knowledge/medical_coding_systems_reference.md) — ICD, CPT, SNOMED differences.
* [`snomed_to_icd_mapping_strategy.md`](./medical_domain_knowledge/snomed_to_icd_mapping_strategy.md) — V1 mappings.
* [`general_knowledge_reference.md`](./medical_domain_knowledge/general_knowledge_reference.md) — Seed data values.
* [`who_icd_integration_plan.md`](./medical_domain_knowledge/who_icd_integration_plan.md) — Why and how we use the WHO API.
* [`who_icd_api_technical_reference.md`](./medical_domain_knowledge/who_icd_api_technical_reference.md) — WHO API endpoints and OAuth.

## 🏃‍♂️ 5. Sprints & Progress
*Historical tracking, agile plans, and future roadmaps.*
* [`master_sprint_plan.md`](./sprints_and_progress/master_sprint_plan.md) — The timeline.
* [`foundation_implementation_log.md`](./sprints_and_progress/foundation_implementation_log.md) — Initial build notes.
* [`build_progress_tracker.md`](./sprints_and_progress/build_progress_tracker.md) — Phase closures.
* [`phases_3_to_7_copilot_handoff.md`](./sprints_and_progress/phases_3_to_7_copilot_handoff.md) — Next steps for the backend.
* [`backend_bugs_and_fixes.md`](./sprints_and_progress/backend_bugs_and_fixes.md) — Known backend issues and resolutions.
* [`frontend_bugs_and_fixes.md`](./sprints_and_progress/frontend_bugs_and_fixes.md) — Known frontend issues and resolutions.
* **Feature Sprints:** Detailed plans inside `sprint1` through `sprint7` subdirectories under this domain.
