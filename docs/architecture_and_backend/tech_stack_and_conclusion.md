## 4. Component Details & Technology Stack

### 4.1 Technology Stack Summary

| Component | Technology | Rationale |
| :--- | :--- | :--- |
| **Frontend Framework** | Next.js (React), TailwindCSS, Shadcn UI | Provides React Server Components for fast initial loads, robust ecosystem, and premium UI components. |
| **Backend API** | FastAPI (Python 3.11+) | Asynchronous Python framework optimal for high-throughput AI workloads and LLM processing. |
| **AI Orchestration** | LangGraph | Extends LangChain to build stateful, multi-agent pipelines with complex conditional routing and memory. |
| **LLM Engine** | LLaMA 3.3-70B via Groq | Extreme inference speed (LPU) necessary for near-instant clinical text extraction. |
| **Coding Engine** | WHO ICD API v2 (v2.6) | Official Source of Truth for ICD-11/ICD-10; ensures 100% compliance with ABDM mandates. |
| **Database & Auth** | Supabase (PostgreSQL) | Provides seamless JWT authentication, Row-Level Security (RLS) for multi-tenancy, and `pgvector` for embedding searches. |
| **Document Parsing** | pdfplumber, Tesseract OCR | Hybrid parsing combining native PDF text extraction with optical character recognition for scanned records. |
| **Cloud Hosting** | GCP Cloud Run, Vercel | Serverless architecture reduces idle costs to zero while securely scaling out during traffic spikes. Hosted in Mumbai for data residency. |

### 4.2 Database Schema Overview (Core Tables)
Integronix relies on a highly structured relational database optimized for fast reads and secure multi-tenant isolation.
*   **organizations:** Master tenant table.
*   **branches:** Geographic or logical subsets within an organization.
*   **users / user_profiles:** Maps Supabase Auth identities to specific organizations and branches.
*   **clinical_cases:** Stores the raw text, the final ICD code, AI confidence scores, risk metrics, and the auto-generated FHIR Condition JSON. Row-Level Security (RLS) guarantees hospital data isolation.
*   **org_settings:** Runtime configuration controlling ICD-11 vs ICD-10 preference, coding aggressiveness, and the insurance claim scheme context per hospital.
*   **icd_codes:** A warm cache for the WHO API returns, enriched with local DRG base reimbursement values and Complication/Comorbidity (CC/MCC) flags.

### 4.3 Conclusion
The Integronix architecture represents a paradigm shift in medical coding infrastructure. By moving away from static, easily-outdated databases and directly integrating with the WHO's live ICD classification APIs—all orchestrated by a deterministic LangGraph AI pipeline—the system ensures maximum accuracy, auditability, and compliance with the Ayushman Bharat Digital Mission. The strict multi-tenant data layer guarantees patient data privacy, making Integronix a production-ready solution for modern Indian hospitals.
