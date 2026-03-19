# Technology Stack & Architectural Conclusion

This document provides a summary of the technology stack used to build Integronix and concludes with the core architectural principles that guide the system's design.

---

## 1. Technology Stack

| Component | Technology / Service | Rationale & Key Usage |
| :--- | :--- | :--- |
| **Frontend** | Next.js (React), Tailwind CSS | Modern, high-performance web framework for building the user dashboard and interactive components. |
| **Backend API** | FastAPI (Python 3.11+) | High-performance, asynchronous Python framework ideal for I/O-bound and AI-heavy workloads. |
| **AI Orchestration** | LangGraph | Powers the stateful, multi-agent pipeline, enabling complex conditional routing and robust error handling. |
| **LLM Engine** | Groq API (Llama 3) | Provides extreme low-latency inference for the initial `clinical_extractor` node, enabling near-real-time text analysis. |
| **Primary Coding Source** | WHO ICD-API v2 | The official, compliant source for ICD-11 and ICD-10 lookups, ensuring maximum accuracy and adherence to standards. |
| **Database** | Supabase (PostgreSQL 16) | Managed PostgreSQL service providing authentication, Row-Level Security (RLS), and database functions. |
| **Vector Search** | `pgvector` extension | Enables high-speed cosine similarity search for the semantic fallback mechanism within the `icd_embedding_node`. |
| **Vector Embeddings** | `sentence-transformers` | The `all-MiniLM-L6-v2` model is used for its optimal balance of speed and quality in generating 384-dimension embeddings. |
| **Document Parsing** | `pdfplumber` | Efficiently extracts text and metadata directly from PDF documents. |
| **Containerization** | Docker, Docker Compose | Used for creating reproducible development and production environments. |

---

## 2. Core Architectural Principles

The Integronix architecture is built upon a foundation of five key principles that ensure it is accurate, robust, secure, and auditable.

### I. Hybrid AI Model
The system intelligently blends the strengths of Large Language Models (LLMs) with the reliability of deterministic algorithms. An LLM is used for what it does best: understanding and structuring unstructured clinical text. However, all subsequent steps—and most importantly, the final ICD code selection—are handled by deterministic, rule-based logic.

### II. Deterministic by Default
The final, billable decision is **never** left to a non-deterministic "guess" by an LLM. The `icd_decision_node` applies a transparent, weighted scoring algorithm. This guarantees that given the same input and the same candidate list, the output will always be the same. This principle is paramount for clinical and financial accuracy.

### III. Robustness Through Fallbacks
The architecture is designed to be resilient and to always produce a result. The ICD resolution process follows a graceful degradation path:
1.  **Primary Path**: Attempt to use the official **WHO ICD API**.
2.  **Secondary Path**: If that fails or is not applicable, attempt a direct **SNOMED-to-ICD-10 crosswalk** from our internal database.
3.  **Tertiary Path**: If that also fails, execute a **semantic vector search** to find the most similar codes.
This ensures maximum coverage and prevents silent failures.

### IV. Auditability and Traceability
Every step of the agent's "thought process" is recorded in the `CodingState` object as it passes through the graph. Key data points like `mapping_path` and the final `decision_trace` object provide a clear, auditable trail that explains exactly *how* and *why* a specific code was chosen over others.

### V. Secure Multi-Tenancy
Data privacy and security are not an afterthought. The system is built from the ground up on Supabase's Row-Level Security (RLS). Every database query is automatically filtered by the authenticated user's `org_id`, making it architecturally impossible for one organization to access another's data.

---

## 3. Conclusion

The Integronix architecture represents a significant evolution in medical coding technology. By combining a state-of-the-art AI orchestration engine with a multi-layered, fallback-driven approach, it achieves a rare balance of speed, accuracy, and compliance. Its deterministic decision core provides the reliability required for financial and clinical systems, while its auditable and secure data layer makes it a trustworthy, enterprise-ready solution for healthcare providers. This is not just an AI tool; it is a robust, intelligent, and safe system designed for the complexities of the real world.

