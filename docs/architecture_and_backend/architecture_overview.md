# Architecture Overview

## Architecture Philosophy

Our architectural philosophy is centered on a hybrid approach that leverages the strengths of Large Language Models (LLMs) for what they do best—understanding and reasoning over unstructured text—while relying on deterministic, rule-based engines for tasks that require 100% accuracy and auditability.

- **LLM for Reasoning, Not for Final Decisions**: We use a powerful LLM (via Groq) exclusively for the initial, high-level task of clinical entity extraction. It reads the unstructured clinical notes and identifies potential diagnoses, procedures, and clinical concepts. It does **not** select the final billable code.
- **Deterministic Engine for Code Selection**: The final selection of an ICD code is performed by a deterministic Python-based engine. This engine uses a scoring algorithm based on factors like code specificity, negation detection, and frequency. This guarantees that the output is repeatable, explainable, and free from the risk of LLM "hallucinations."
- **Agentic Orchestration with LangGraph**: The entire multi-step workflow is managed as a stateful graph using LangGraph. This allows for complex, conditional routing (e.g., "if ICD-11, use WHO API; if ICD-10, use local mapping") and ensures each step of the process is tracked and auditable.
- **API-First and Decoupled Design**: The system is built with an API-first approach using FastAPI. The frontend (Next.js) is completely decoupled from the backend logic, communicating solely through a well-defined REST API. This allows for independent development, scaling, and maintenance of the user interface and the core engine.
- **Hybrid Search Strategy**: We employ a multi-layered search strategy. The primary path involves direct mapping (SNOMED to ICD-10) or API calls (WHO ICD-11). If these yield no results, the system automatically falls back to a powerful semantic search using vector embeddings (`pgvector`) to find the closest match based on clinical meaning.

---

## System Architecture Diagram

A detailed, interactive diagram of the complete system architecture is available in the central diagrams document. This diagram provides a comprehensive overview of the frontend, backend services, data layer, and external API integrations.

**[View Complete System Architecture Diagram](./diagrams.md#2-system-architecture-diagram)**

---

## Layer Breakdown

### 1. Presentation Layer (Next.js Frontend)
This is the user-facing application where hospital administrators, coders, and auditors interact with the system.
- **Onboarding & Configuration**: Administrators can set up their organization, manage users, and configure crucial settings like the target ICD version (ICD-10 or ICD-11) and claim scheme.
- **Document Upload**: Coders can upload clinical documents in various formats (e.g., PDF, text) for analysis.
- **Interactive Dashboard**: The primary interface for coders, displaying the extracted clinical summary, the system's suggested ICD/CPT codes, confidence scores, and the results of an audit against human-provided codes.
- **Analytics & Reporting**: Views for auditors to analyze risk scores, potential financial impact, and historical coding accuracy.

### 2. API Layer (FastAPI)
This layer exposes the system's functionality via a secure and robust REST API. It is the single entry point for the frontend.
- **`POST /code/run`**: The primary endpoint for text-based analysis. It accepts a clinical summary and organization settings, then initiates the full LangGraph pipeline.
- **`POST /code/run-pdf`**: A convenience endpoint that first extracts text from an uploaded PDF and then passes it to the main pipeline.
- **`GET /cases`**: Endpoints for retrieving historical cases, their status, and detailed results.
- **`GET /analytics`**: Endpoints to power the reporting and analytics dashboards.
- **Authentication**: All endpoints are secured using a robust authentication mechanism (e.g., JWT) to ensure data privacy and security.

### 3. Agent Orchestration Layer (LangGraph)
This is the core of the backend, where the complex logic of medical coding is executed as a series of interconnected nodes in a stateful graph.
- **Stateful `CodingState` Object**: A central Python object (`TypedDict`) that carries all data—from the initial clinical text to the final audit results—as it flows through the graph.
- **Conditional Routing**: The graph contains intelligent, conditional edges that dynamically alter the path of execution based on the data. For example, it routes to the `ICD_Embedding_Node` only if the primary mapping nodes fail to find a code. It routes to the `WHO_ICD_Service` if the organization is configured for ICD-11.
- **Specialized Nodes**: Each node is a Python function with a single responsibility (e.g., `clinical_extractor`, `snomed_resolver`, `icd_decision`). This modularity makes the system easy to test, debug, and extend.
- **Full details of the agent pipeline are available here: [View Agent Architecture Diagram](./diagrams.md#3-agent-architecture-diagram-langgraph-pipeline)**

### 4. Data Layer (PostgreSQL + pgvector)
The persistence layer, built on the reliable and powerful PostgreSQL database, managed via Supabase for ease of use and scalability.
- **`organizations`, `users`, `cases`, `claims`**: Core tables for managing multi-tenant data, user access, and individual coding cases. The `cases` table stores the full `CodingState` object for complete auditability.
- **`cpt_codes`, `icd10_codes`**: Curated datasets for CPT and ICD-10 codes, including their descriptions.
- **`snomed_icd_map`**: The crucial mapping table for converting SNOMED-CT concepts directly to ICD-10 codes.
- **`pgvector` Extension**: This powerful extension turns PostgreSQL into a high-performance vector database. It stores the 384-dimension embeddings of all ICD codes and enables the semantic search fallback mechanism.
- **A detailed schema is available here: [View Database ER Diagram](./diagrams.md#4-database-er-diagram)**

### 5. External Services
The system integrates with best-in-class external services to perform specialized tasks.
- **Groq API**: Provides access to a high-speed LLM (Llama 3) for the clinical extraction step, chosen for its extremely low latency.
- **WHO ICD-11 API**: The official and authoritative source for ICD-11 and ICD-10 lookups, used when specified by the organization's settings.
- **SentenceTransformers**: A Python library used during an offline process to generate the high-quality vector embeddings for our semantic search feature.

---

## Technology Choices & Justification

| Technology | Purpose | Why |
|---|---|---|
| **FastAPI** | API Layer | High performance (async), automatic OpenAPI/Swagger documentation, and native Pydantic integration for robust data validation. |
| **LangGraph** | Agent Orchestration | Provides a powerful, explicit, and debuggable way to build stateful, multi-agent workflows with complex conditional logic. Essential for our hybrid model. |
| **Groq** | LLM Inference | Delivers unparalleled low-latency inference, which is critical for a responsive user experience in a real-time coding tool. |
| **PostgreSQL** | Primary Database | The gold standard for reliability, data integrity (ACID compliance), and extensibility, making it ideal for storing sensitive clinical and financial data. |
| **pgvector** | Semantic Search | A mature and high-performance vector search solution that integrates seamlessly into our existing PostgreSQL database, avoiding the need for a separate vector DB. |
| **Pydantic** | Data Validation | Enforces strict, structured data models throughout the application, especially for validating the output from the LLM before it is used by downstream deterministic nodes. |
| **Next.js** | Frontend | A modern, high-performance React framework that enables the creation of fast, interactive, and server-rendered user interfaces perfect for dashboards. |
| **Docker Compose** | Development & Deployment | Ensures consistency between development and production environments and simplifies the deployment of our multi-service application. |

---

## Security Considerations

| Concern | Approach |
|---|---|
| **PHI (Protected Health Information)** | All sensitive data is encrypted at rest and in transit. We enforce a strict policy of not logging raw clinical text in production environments to minimize exposure. Access is tightly controlled via role-based access control (RBAC). |
| **API Security** | All API endpoints are protected with JWT-based authentication and authorization. Each request is validated to ensure the user belongs to the correct organization and has the necessary permissions. |
| **LLM Output Validation** | The unstructured output from the LLM is immediately passed through a strict Pydantic model. If the output does not conform to the expected schema, the process is halted, preventing corrupted or malicious data from propagating. |
| **Code Integrity** | The LLM is never allowed to invent or inject codes. The final ICD code is always selected from our curated, internal database, which is the single source of truth. |
| **Audit Logging** | Every coding session, including the full state at each step of the LangGraph pipeline, is saved to the `cases` table. This provides a complete, immutable audit trail for traceability and compliance. |

> **Note:** The current implementation provides a strong security foundation. Full production deployment will undergo a rigorous third-party audit to ensure full HIPAA compliance.

---

## Scalability Discussion

The system is designed with scalability in mind from day one.

- **Stateless API**: The FastAPI application is stateless, allowing it to be scaled horizontally by simply adding more container instances behind a load balancer.
- **Asynchronous Job Queues**: For production scale, the LangGraph workflows, which can be long-running, will be offloaded to a distributed task queue like Celery with Redis or RabbitMQ as a broker. This prevents API timeouts and allows for resilient, scalable processing.
- **Database Scaling**: The PostgreSQL database can be scaled effectively. For read-heavy workloads (like analytics), read replicas can be added. For write-heavy workloads, partitioning and other advanced scaling strategies can be employed.
- **Managed Services**: Leveraging Supabase for the database and a managed container service (like AWS ECS, Azure Container Apps, or Google Cloud Run) for the backend will handle auto-scaling, monitoring, and maintenance.

---

## Future Roadmap

This outlines the planned evolution of the Integronix platform.

| Phase | Feature | Description |
|---|---|---|
| **Phase 1 (Current)** | **Core Hybrid Engine POC** | Establish the core pipeline: PDF/text parsing, LLM-based clinical extraction, deterministic ICD-10 mapping, audit comparison, and foundational risk/revenue calculation. |
| **Phase 2** | **Full Code Set & ICD-11 Parity** | Ingest the complete ICD-10-CM and CPT code sets. Fully operationalize the WHO API integration for a seamless ICD-11 coding experience, making it feature-complete with the ICD-10 path. |
| **Phase 3** | **Advanced Rules Engines** | Integrate a full DRG (Diagnosis-Related Group) grouper to provide accurate financial impact analysis. Implement an NCCI (National Correct Coding Initiative) engine to validate code bundling and prevent common claim denials. |
| **Phase 4** | **Payer-Specific Logic & Multi-Tenancy** | Develop a rules engine to incorporate logic specific to different insurance payers. Enhance the multi-tenant architecture to support large hospital networks with isolated data and configurations. |
| **Phase 5** | **Advanced AI & Analytics** | Introduce more advanced AI features, such as predictive analytics for claim denial risk, automated appeals generation, and deeper insights into coder performance and accuracy trends across the organization. |

