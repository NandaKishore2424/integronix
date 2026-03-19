# System Architecture

## 2.1 Architectural Overview
The Integronix system is engineered on a modern, cloud-native, and API-first architecture designed for high performance, scalability, and robust security. The architecture is logically segmented into four primary tiers, ensuring a clear separation of concerns and enabling independent development and scaling of each component.

1.  **Presentation Layer (Frontend)**: A responsive and interactive web application built with Next.js, providing the user interface for administrators, coders, and auditors.
2.  **Application & API Layer (Backend)**: A high-performance backend built with Python and FastAPI, which exposes a RESTful API and serves as the gateway to the core intelligence of the system.
3.  **Agentic AI Pipeline (LangGraph)**: The heart of the system. A sophisticated, stateful workflow built with LangGraph that orchestrates a series of specialized agents to perform the end-to-end medical coding and auditing process.
4.  **Data & Persistence Layer**: A secure and scalable data store built on PostgreSQL and managed via Supabase, handling structured data, user information, multi-tenancy, and the powerful `pgvector` extension for semantic search.

## 2.2 System Architecture Diagram

The following diagram provides a high-level, comprehensive visualization of the Integronix system architecture, illustrating the flow of data and control from the user's browser through the various backend components and external services.

**[View Detailed System Architecture Diagram](./diagrams.md#2-system-architecture-diagram)**

---

## 2.3 Component Descriptions

### 2.3.1 Presentation Layer (Frontend)
The entire user experience is delivered through a modern web application built with **Next.js** (a React framework). This choice enables a fast, responsive, and feature-rich Single-Page Application (SPA) experience.
- **Hosting**: The frontend is designed for easy deployment on serverless platforms like Vercel or Netlify, which provide automatic scaling, global distribution (CDN), and integrated CI/CD pipelines.
- **Communication**: The frontend is completely decoupled from the backend logic. It communicates exclusively with the API Layer via secure HTTPS requests, ensuring no direct access to the database or internal services from the client-side.
- **Key Features**:
    - Organization and user management consoles for administrators.
    - A secure file upload interface for clinical documents.
    - An interactive dashboard for coders to review AI-generated codes, audit results, and evidence from the clinical text.

### 2.3.2 Application & API Layer (Backend)
The backend is a high-performance asynchronous application built with **Python 3.11+** and the **FastAPI** framework. It serves as the single, unified entry point for all client requests.
- **API Gateway**: It exposes a clean, versioned REST API (e.g., `/api/v1/...`). Key endpoints like `POST /code/run` and `POST /code/run-pdf` trigger the entire agentic pipeline.
- **Security**: Security is paramount. The API layer enforces authentication and authorization on all protected endpoints, typically using JWTs. It integrates with Supabase Auth to validate tokens and retrieve user roles and organization affiliations.
- **Pydantic Validation**: All incoming request bodies and outgoing responses are rigorously validated against Pydantic models, preventing data-related errors and ensuring a consistent API contract.
- **Containerization**: The entire backend application is containerized using **Docker**, making it portable, scalable, and easy to deploy in any environment, from local development (via `docker-compose`) to cloud-based container orchestrators.

### 2.3.3 Agentic AI Pipeline (LangGraph)
This is the core intelligence of Integronix. Instead of a simple, linear script, we use **LangGraph** to define a stateful, graph-based workflow. This allows for complex, conditional logic that mirrors the real-world process of medical coding.
- **State Management**: A central `CodingState` object persists throughout the workflow, carrying data from one node to the next. This provides a complete, auditable trace of the entire process.
- **Specialized Nodes**: The graph consists of 10 distinct, specialized nodes, each with a single responsibility. This modular design is key to the system's accuracy and maintainability.
    1.  **`doc_processing`**: Extracts clean text from uploaded documents, with OCR fallback for scanned images.
    2.  **`clinical_extractor`**: Uses a powerful LLM (via the **Groq API** for low latency) to perform natural language understanding and extract structured clinical entities.
    3.  **`cpt_resolver`**: Performs semantic search to find relevant CPT codes.
    4.  **`snomed_resolver`**: The primary routing node. It checks the organization's settings and decides whether to use the **WHO ICD-11 API** or proceed with the local SNOMED-to-ICD-10 mapping path.
    5.  **`snomed_icd_map`**: Performs a direct database lookup to crosswalk a SNOMED code to an ICD-10 code.
    6.  **`icd_embedding` (Fallback)**: A crucial fallback mechanism. If the primary paths fail, this node uses vector similarity search (`pgvector`) to find semantically related codes.
    7.  **`icd_decision`**: A fully **deterministic**, rule-based engine that selects the final, most accurate code from the candidates. It does **not** use an LLM, ensuring explainable and repeatable results.
    8.  **`audit_comparison`**: Compares the AI's code against a human-provided code.
    9.  **`risk_scoring`**: Calculates a compliance risk score based on the audit findings.
    10. **`financial_calculator`**: Determines the financial impact of any coding discrepancies.

**[View Detailed Agent Pipeline Diagram](./diagrams.md#3-agent-architecture-diagram-langgraph-pipeline)**

### 2.3.4 Data & Persistence Layer (PostgreSQL + Supabase)
The foundation of our data layer is a robust **PostgreSQL** database, which we manage and access through **Supabase**. Supabase provides a suite of tools that simplify database management, authentication, and security.
- **Multi-Tenancy & Security**: The database is designed for multi-tenancy from the ground up. We leverage PostgreSQL's **Row-Level Security (RLS)** to enforce strict data isolation. This ensures that users from one organization can *never* access the data of another, even if they are in the same database.
- **Core Schema**: The schema includes tables for `organizations`, `users`, `cases` (which stores the full, serialized `CodingState` for auditability), and `claims`.
- **Coding & Mapping Data**: It also houses the curated datasets for `cpt_codes`, `icd10_codes`, and the `snomed_icd_map`.
- **Vector Database (`pgvector`)**: We use the `pgvector` extension, which transforms our PostgreSQL instance into a powerful and efficient vector database. It stores the 384-dimension embeddings of all codes and enables the high-speed semantic search used in our fallback mechanisms. This integrated approach avoids the complexity and cost of maintaining a separate vector database.

**[View Detailed Database ER Diagram](./diagrams.md#4-database-er-diagram)**

