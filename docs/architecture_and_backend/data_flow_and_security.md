## 3. Data Flow and Integration Patterns

### 3.1 End-to-End Data Pipeline

1. **Ingestion & Authentication:** A client (e.g., hospital user) uploads a clinical text or PDF payload to the Next.js frontend, appending their authorization JWT provided via Supabase Auth. 
2. **Context Resolution:** The FastAPI backend receives the request at `/code/run` or `/code/run-pdf`. It decodes the JWT to identify the user's `organization_id` and query the `org_settings` table to determine the relevant `icd_version` (ICD-11 vs ICD-10).
3. **Document Processing (Node 1):** Raw bytes are pushed either through standard parsers or an OCR pipeline (Tesseract) to derive clean text.
4. **Information Extraction (Node 2):** The text is transmitted via a secure REST call to the Groq Cloud endpoint. The LLaMA 3.3-70B model parses the document and returns structured JSON (diagnoses, medications, procedures, patient demographics).
5. **Coding Resolution (Nodes 3-5):**
    * **WHO API Primary:** Node 3 immediately pings the WHO ICD API (v2) securely using an OAuth2 cached Client Credentials token. If `org_settings.icd_version` = "ICD-11", the MMS linearization search endpoint is used. If "ICD-10", the Foundation Autocode endpoint is used.
    * **Fallback 1:** If the WHO API returns zero candidates or is unreachable, Node 3 falls back to a deterministic string-matching pattern against the local SNOMED CT terminology database.
    * **Fallback 2:** If unresolved, Node 4 attempts a standard crosswalk mapping from the SNOMED string to an ICD-10 code.
    * **Fallback 3:** If all else fails, Node 5 translates the clinical text into vector embeddings utilizing `sentence-transformers` (all-MiniLM-L6-v2) and performs an exact similarity (`pgvector` cosine distance) search across the `icd_codes` cache.
6.  **Decision & Output Formulation (Nodes 6-8):** The pipeline aggregates generated candidates, selects the highest probability match as the primary diagnosis code, compares this to an original user-provided code, assigns a risk score to the clinical output, maps the final payload to an HL7 FHIR R4 schema, and persists the payload down to the multi-tenant `clinical_cases` database.
7.  **Final Response:** FastAPI returns the generated `CodeResponse` JSON back to the frontend.

### 3.2 Key Integration: WHO ICD API v2

Integronix natively integrates with the live WHO ICD classification servers (https://id.who.int), displacing standard static database tables.

*   **Authentication Flow:** The API uses an OAuth2 Client Credentials grant (managed in `services/who_icd_service.py`). To prevent rate-limit throttling and minimize roundtrip latency, the Bearer token is cached in-memory using an `asyncio.Lock` mechanism and is auto-refreshed 60 seconds prior to its 3600-second expiry.
*   **Performance Optimization:** The API responses return foundational entity IDs or standard alphanumeric billing codes. To improve speed, Integronix utilizes a "lazy cache":
    * When a code is retrieved from the live WHO server, it is locally upserted into the `icd_codes` database table (Phase 3).
    * Critical metadata that WHO does not provide—specifically CC (Complication or Comorbidity) flags, MCC flags, and DRG Base Reimbursement values—are enriched asynchronously from local databases upon cache retrieval. 

### 3.3 Security & Multi-Tenancy Design Considerations

The architecture adheres strictly to healthcare compliance structures necessary for processing PHI (Protected Health Information).

*   **Tenant Isolation (PostgreSQL RLS):** Security is not managed merely by the API logic; it is enforced directly within the database engine. Supabase Row-Level Security (RLS) policies mandate that the `organization_id` field on tables like `clinical_cases` and `user_profiles` strictly matches the `auth.uid()` mapped identity. Data spillage between Hospital A and Hospital B is algorithmically impossible at queries.
*   **Data Residency & Cloud Deployment:** The containerized backend application is specifically deployed to GCP **Cloud Run in the `asia-south1` (Mumbai) region**, ensuring compliance with Indian data residency mandates for ABHA networks. 
*   **Scaling:** Both Cloud Run (FastAPI) and Vercel (Next.js) utilize serverless autoscaling (to `min-instances: 0` during idle periods) to minimize cost while retaining the capacity to burst instantly during unpredictable traffic loads.
