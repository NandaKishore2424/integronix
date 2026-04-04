# Data Flow and Security

## 3.1 End-to-End Data Pipeline

The flow of data through the Integronix system is a carefully orchestrated process designed for security, accuracy, and auditability. Every step is tracked within the `CodingState` object as it traverses the LangGraph pipeline.

1.  **Ingestion & Authentication (Frontend -> API)**:
    - A user logs into the Next.js web application. Upon successful login, Supabase Auth provides a JSON Web Token (JWT).
    - The user uploads a clinical document (PDF) or pastes raw text.
    - The frontend sends a `POST` request to the appropriate backend endpoint (`/code/run-pdf` or `/code/run`). The request includes the data and the JWT in the `Authorization` header.

2.  **API Gateway & Context Resolution (FastAPI)**:
    - The FastAPI backend receives the request. The first action is to validate the JWT.
    - The user's `id` and `organization_id` are extracted from the validated token.
    - The system queries the `organizations` table to retrieve settings specific to that organization, such as the target `icd_version` (e.g., "icd-10" or "icd-11") and `claim_scheme`.
    - An initial `CodingState` object is created, populating it with this context.

3.  **Document Processing (Node 1)**:
    - If a PDF was uploaded, this deterministic node extracts the raw text. It uses `pdfplumber` for digital PDFs and falls back to Tesseract OCR for scanned documents. The clean text is written to `state.raw_text`.

4.  **Clinical Extraction (Node 2 -> Groq API)**:
    - The `raw_text` is sent via a secure HTTPS call to the Groq Cloud API.
    - The LLM processes the text against a specialized prompt and returns a structured JSON object of clinical entities.
    - **Security**: The returned JSON is immediately validated against a strict Pydantic model. If validation fails, the pipeline halts, preventing malformed or malicious data from proceeding.

5.  **Coding Resolution (Nodes 4, 5, 6)**: This is a multi-step, conditional process.
    - **Path A (ICD-11 via WHO API)**: If `state.icd_version` is "icd-11", the `snomed_resolver_node` makes a secure, authenticated call to the official WHO ICD-11 API. The results are stored in `state.candidate_icd_codes`.
    - **Path B (ICD-10 via SNOMED Map)**: If the version is "icd-10", the `snomed_icd_mapping_node` attempts to find a direct mapping from the resolved SNOMED concepts to ICD-10 codes in the local database.
    - **Path C (Fallback via Vector Search)**: If neither Path A nor Path B produces any candidates, the `_route_after_mapping` conditional edge routes the flow to the `icd_embedding_node`. This node performs a semantic similarity search using `pgvector` to find the closest matching codes.

6.  **Decision & Enrichment (Nodes 7-10)**:
    - The `icd_decision_node` (a deterministic engine) analyzes the `candidate_icd_codes` and selects the final, most accurate code.
    - The `audit_comparison_node` compares this AI code to any human-provided code.
    - The `risk_scoring_node` and `financial_calculator_node` enrich the state with compliance risk and financial impact data.

7.  **Persistence & Response (API -> Frontend)**:
    - The final, enriched `CodingState` object is serialized to JSON and stored in the `cases` table in the PostgreSQL database, creating a permanent, auditable record of the entire transaction.
    - The API formats a clean `CodeResponse` JSON object and sends it back to the frontend as the response to the initial request.

---

## 3.2 Security & Multi-Tenancy by Design

Security is not an afterthought; it is woven into the fabric of the architecture, from the database to the API.

-   **Tenant Isolation with PostgreSQL RLS**: Our multi-tenancy model is enforced at the database level using PostgreSQL's powerful Row-Level Security (RLS).
    -   Every table containing organization-specific data (e.g., `cases`, `claims`) has an `organization_id` column.
    -   RLS policies are defined on these tables, which act as an automatic `WHERE` clause on every single `SELECT`, `INSERT`, `UPDATE`, or `DELETE` query.
    -   The policy ensures that the `organization_id` in the row being accessed **must** match the `organization_id` claim present in the user's JWT.
    -   This makes it architecturally impossible for a query from a user in Hospital A to access data belonging to Hospital B, as the database itself will prevent it. This is far more secure than relying solely on application-layer logic.

-   **Authentication & Authorization**:
    -   **Authentication**: Handled by Supabase Auth. Users log in, and Supabase issues a signed JWT.
    -   **Authorization**: The FastAPI backend acts as a gatekeeper. It validates the JWT on every request. Endpoints can be further restricted based on user roles (e.g., "admin" vs. "coder"), which can also be embedded in the JWT.

-   **Data in Transit**: All communication between the client, the API, and external services (Groq, WHO) is encrypted using industry-standard TLS (HTTPS).

-   **Data at Rest**: All data in the PostgreSQL database is encrypted at rest, a standard feature of most cloud database providers.

-   **Principle of Least Privilege**: The LLM is a prime example of this principle. It is only used for one specific task (clinical extraction) and is never allowed to interact with the database or make final decisions. Its output is immediately contained and validated by a Pydantic model, limiting its "blast radius."

-   **Data Residency**: For compliance with regulations like India's Digital Personal Data Protection Act (DPDPA), the entire infrastructure (application containers, database) can be deployed to a specific geographic region (e.g., `ap-south-1` for Mumbai). The containerized nature of the application makes this straightforward.

-   **Scalability & Availability**:
    -   The stateless nature of the FastAPI backend allows it to be scaled horizontally with ease. Using a serverless container platform (like Google Cloud Run or Azure Container Apps) allows the system to scale from zero to handle traffic bursts, then back down to zero, optimizing costs.
    -   The Supabase/PostgreSQL database can be scaled with read replicas and other standard database scaling techniques to handle increased load.

