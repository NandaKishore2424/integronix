# ICD Integration & Dynamic Routing Logic

This document provides a detailed technical explanation of how the Integronix system handles both ICD-10-CM and ICD-11 coding standards. The core of this functionality is a dynamic routing mechanism that selects the appropriate coding path based on organization-specific settings.

See the [System Architecture Diagram](diagrams.md#system-architecture-diagram) for a visual overview.

---

## 1. The Routing Decision: `org_settings`

At the very beginning of every coding pipeline run, the system fetches the configuration for the client's organization from the `org_settings` table. Two columns are critical for routing:

-   `icd_version`: Can be `'ICD-10'` or `'ICD-11'`.
-   `claim_scheme`: A string indicating the billing standard (e.g., `'default'`, `'ayushman'`, `'cghs'`).

This information is injected into the `CodingState` and used by the `snomed_resolver` node to make a crucial decision, as detailed in the [SNOMED Flow documentation](langgraph_snomed_flow.md).

The logic is simple but powerful:
```python
# In backend/agents/snomed_resolver.py
use_who_api = bool(
    (claim_scheme in {"ayushman", "cghs"}) or (icd_version == "ICD-11")
)
```

This boolean flag dictates whether to use the modern WHO API or our internal ICD-10 database.

---

## 2. Path A: The ICD-11 / WHO API Workflow

When `use_who_api` is `True`, the system uses our `who_icd_service` to connect to the official WHO ICD-API v2. This is the preferred path for accuracy and compliance with modern standards.

### 2.1 Request Flow

1.  **Service Called**: `snomed_resolver_node` calls `who_icd_service.search_icd()`.
2.  **Authentication**: The service transparently handles OAuth2 authentication with the WHO API, requesting a token using our client credentials and caching it for subsequent requests to minimize latency.
3.  **API Request**: It constructs a `GET` request to the WHO API's `/icd/release/11/.../search` endpoint.
    *   **URL Parameters**: The primary parameter is `q={diagnosis_text}`, where `diagnosis_text` is the clinical term extracted by the `clinical_extractor` node.
    *   **Headers**: Includes the `Authorization: Bearer {access_token}` and `API-Version: v2` headers.

### 2.2 Response Flow

1.  **WHO API Response**: The WHO API returns a JSON object containing a list of `destinationEntities`. Each entity represents a potential ICD-11 code match. A simplified example of the response for the query "Cholera" is:
    ```json
    {
      "destinationEntities": [
        {
          "id": "http://id.who.int/icd/entity/1335340813",
          "title": "<b>Cholera</b>",
          "theCode": "1A00",
          "score": 13.952816
        },
        {
          "id": "http://id.who.int/icd/entity/1296093773",
          "title": "Classical <b>cholera</b>",
          "theCode": "1A00.0",
          "score": 12.74399
        }
      ]
    }
    ```
2.  **Internal Processing**: Our `who_icd_service` parses this response.
3.  **Data Enrichment**: For each result, it queries our internal `icd_codes` database table to fetch additional metadata that the WHO API does not provide, such as `is_cc`, `is_mcc`, and `base_reimbursement` values.
4.  **State Update**: The enriched list of candidates is used to populate `state.candidate_icd_codes`. The `mapping_path` is set to `"who_api_icd11"` or `"who_api_icd10"`.

The workflow then proceeds directly to the `icd_decision_node`, bypassing all SNOMED and embedding steps.

---

## 3. Path B: The ICD-10-CM / Internal Database Workflow

When `use_who_api` is `False`, the system relies entirely on our internal, pre-processed ICD-10-CM database.

### 3.1 Data Sources & Ingestion

The internal database is built from official ICD-10-CM data files. The ingestion pipeline is detailed in the [ICD-10-CM Ingestion Pipeline document](icd10cm_ingestion_pipeline.md). The key tables used in this workflow are:

-   `icd_codes`: The master list of all 98,000+ ICD-10-CM codes, their descriptions, and our calculated flags (`is_billable`, `is_cc`, `is_mcc`). This table also contains the vector embeddings for semantic search.
-   `snomed_concepts`: A table of SNOMED-CT concept IDs and their descriptions.
-   `snomed_icd_map`: A crucial crosswalk table that maps SNOMED-CT concepts directly to ICD-10-CM codes.

### 3.2 Request & Response Flow (Internal)

This path involves a sequence of internal database queries across multiple graph nodes:

1.  **SNOMED Resolution (`snomed_resolver_node`)**:
    *   **Request**: Takes the LLM-suggested SNOMED code from `state.structured_entities`.
    *   **Action**: Queries the `snomed_concepts` table to validate the code.
    *   **Response**: Populates `state.resolved_snomed_code`.

2.  **SNOMED-to-ICD Mapping (`snomed_icd_map_node`)**:
    *   **Request**: Uses `state.resolved_snomed_code`.
    *   **Action**: Performs a `JOIN` between `snomed_icd_map` and `icd_codes` to find all linked, billable ICD-10-CM codes.
    *   **Response**: If mappings are found, `state.candidate_icd_codes` is populated, and `mapping_path` is set to `"direct"`.

3.  **Embedding Fallback (`icd_embedding_node`)**:
    *   **Condition**: This node only runs if the SNOMED mapping step returns zero candidates.
    *   **Request**: Uses the original `diagnosis_text`.
    *   **Action**: Generates a vector embedding of the text and performs a cosine similarity search against the `embedding` column in the `icd_codes` table using `pgvector`.
    *   **Response**: Populates `state.candidate_icd_codes` with the top 5 most similar results and sets `mapping_path` to `"embedding_fallback"`.

Finally, just like in Path A, the populated `candidate_icd_codes` list is passed to the `icd_decision_node` for final selection. This dual-path, fallback-heavy architecture ensures both compliance with modern standards and robustness for legacy systems.

**Output:** `structured_entities`, `extraction_metadata`
**LLM** (Groq)

### Node 3 — SNOMED / WHO Resolver
**Input:** `structured_entities`, `icd_version`
**Output:** `resolved_snomed_code`, `candidate_icd_codes` (ICD-11 when WHO is used)
**Deterministic + external API**

### Node 4 — SNOMED → ICD Map
**Input:** `resolved_snomed_code`
**Output:** `candidate_icd_codes`
**Deterministic**

### Node 5 — Embedding Fallback
**Input:** `structured_entities`
**Output:** `candidate_icd_codes`
**Deterministic**

### Node 6 — ICD Decision
**Input:** `candidate_icd_codes`, `structured_entities`
**Output:** `final_icd_code`, `confidence_score`, `icd_codes` (multi-code)
**Deterministic**

### Node 7 — Audit Comparison (Conditional)
**Input:** `final_icd_code`, `human_icd_code`
**Output:** `discrepancy_type`, `discrepancy`, `financial_delta`
**Deterministic**

### Node 8 — Risk Scoring + FHIR
**Input:** `final_icd_code`, `discrepancy`
**Output:** `risk_score`, `risk_label`, `fhir_condition`, DB write
**Deterministic**

---

## 5) Candidate Definition
A **candidate** is a potential ICD code with metadata used for ranking:
- `code`, `description`, `icd_version`
- `mapping_type` (exact / narrower / broader / approximate)
- `confidence` / `similarity_score`
- `is_cc` / `is_mcc`, `base_reimbursement`

Candidates can be produced by:
- WHO ICD API
- SNOMED crosswalk
- Embedding similarity search
- Provider fallback (Phase 3)

---

## 6) Accuracy & Confidence (Important Clarification)

**Accuracy** is not explicitly measured in code; instead we expose **confidence** based on deterministic scoring + mapping quality. Key points:
- The system **does not output a code unless it exists in the DB**.
- **Confidence score** reflects ranking strength, not clinical ground‑truth accuracy.
- For production, accuracy must be validated with labeled datasets and QA audits.

---

## 7) Current Outputs Added
- **decision_trace** on API response
- **mapping_path** indicates which pipeline path was used
- **icd_codes** list includes primary/secondary/additional codes

---

## 8) Files Added/Updated (Summary)
- ICD ingestion + parsers + loaders (services + scripts)
- Routing provider (ICD-10 vs ICD-11)
- Updated LangGraph state and nodes
- Decision trace in responses

---

If you want this split into separate docs per node, or want diagrams, say the word and I’ll generate them.