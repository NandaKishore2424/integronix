# The ICD Resolution Flow: WHO API, SNOMED, and Vector Search

The core of the Integronix engine's accuracy lies in its intelligent, multi-layered approach to resolving a clinical diagnosis into a final, billable ICD code. This is not a single step but a sophisticated, conditional workflow orchestrated by LangGraph, primarily centered around the `snomed_resolver` and `snomed_icd_map` nodes.

This document details that critical flow.

---

## The `snomed_resolver` Node: The Grand Central Station

Think of the `snomed_resolver_node` not just as a "SNOMED resolver," but as the **primary routing agent** for all ICD code resolution. Its first and most important job is to decide *which path* to take based on the organization's settings.

The logic, found in `backend/agents/snomed_resolver.py`, is as follows:

1.  **Check the Context**: The node reads `state.icd_version` and `state.claim_scheme` from the `CodingState` object. These values are determined by the `organization`'s settings in the database when the pipeline is initiated.

2.  **Make the Routing Decision**: It determines if it should use the modern WHO API path with a boolean flag:
    ```python
    use_who_api = bool(
        (claim_scheme in {"ayushman", "cghs"}) or (icd_version == "ICD-11")
    )
    ```
    This means the system defaults to the official WHO API for any organization configured for ICD-11 or specific Indian claim schemes, ensuring compliance and accuracy.

---

## Path A: The WHO API Primary Route (The "Happy Path")

If `use_who_api` is `True`, the pipeline executes the following steps within the `snomed_resolver_node`:

1.  **Call `who_icd_service`**: The node calls our internal `search_icd` service, which handles authentication (OAuth2 with token caching) and makes a secure HTTPS request to the official WHO ICD API v2. It sends the `diagnosis_text` from the LLM's extraction as the query.

2.  **Process Results**: The WHO API returns a ranked list of ICD code candidates, complete with descriptions and confidence scores.

3.  **Enrich Data**: The returned codes are then enriched with our internal data (from the `icd_codes` table), adding crucial flags like `is_cc` (Complication or Comorbidity) and `is_mcc`, which the WHO API does not provide.

4.  **Update State**: The node populates the `state.candidate_icd_codes` list directly with these enriched results. It also sets `state.mapping_path` to `"who_api_icd11"` or `"who_api_icd10"` to record how the codes were found.

5.  **Bypass Subsequent Nodes**: Because `candidate_icd_codes` is now populated, the `snomed_icd_map` node will be skipped, and the conditional edge `_route_after_mapping` will route the workflow **directly to the `icd_decision_node`**. The SNOMED and embedding fallback steps are completely bypassed.

This is the most efficient and accurate path for ICD-11 coding.

---

## Path B: The SNOMED Fallback Route (For ICD-10 and Legacy Systems)

If `use_who_api` is `False`, or if the WHO API call fails or returns zero results, the system gracefully falls back to the legacy SNOMED-based workflow.

### Step 1: SNOMED Concept Resolution (`snomed_resolver_node`)

The `snomed_resolver_node` now executes its *second* responsibility: finding a SNOMED-CT concept ID.

1.  **Check LLM Suggestion**: The `clinical_extractor` node asks the LLM to suggest a potential SNOMED code. The `snomed_resolver` first checks if this suggested code is valid by looking it up in our `snomed_concepts` database table. If it's a valid, active code, it's used.
2.  **Text Search Fallback**: If the LLM suggestion is invalid or missing, the node performs a targeted text search against the `description` column of the `snomed_concepts` table to find a match.
3.  **Update State**: The validated SNOMED code and description are written to `state.resolved_snomed_code` and `state.resolved_snomed_desc`.

### Step 2: SNOMED-to-ICD-10 Mapping (`snomed_icd_mapping_node`)

The workflow now proceeds to the next node, `snomed_icd_mapping_node`.

1.  **Database Crosswalk**: This node takes the `resolved_snomed_code` and queries the `snomed_icd_map` table. This table contains pre-defined, curated mappings between SNOMED-CT concepts and ICD-10-CM codes.
2.  **Populate Candidates**: If one or more mappings are found, it fetches the full details for each ICD-10 code (description, billable status, CC/MCC flags) and populates the `state.candidate_icd_codes` list. It sets the `mapping_path` to `"direct"`.

---

## Path C: The Final Fallback - Vector Embedding Search

What if the SNOMED mapping also fails to find any candidates? This is where the conditional edge `_route_after_mapping` becomes critical.

1.  **Check for Candidates**: The conditional edge function checks if `state.candidate_icd_codes` is empty.
2.  **Route to `icd_embedding`**: If it's empty, the graph routes the workflow to the `icd_embedding_node`.
3.  **Perform Semantic Search**: This node takes the original `diagnosis_text`, generates a 384-dimension vector embedding, and uses `pgvector` to perform a cosine similarity search against all the embeddings in the `icd_codes` table.
4.  **Populate Candidates**: It populates `state.candidate_icd_codes` with the top 5 most semantically similar codes and sets the `mapping_path` to `"embedding_fallback"`.

## Convergence at the `icd_decision_node`

No matter which path was taken—WHO API, SNOMED direct map, or embedding fallback—the result is the same: a populated `candidate_icd_codes` list.

The workflow now converges on the `icd_decision_node`, which is completely agnostic to how the candidates were found. It simply applies its deterministic scoring algorithm to the list and selects the best one. This elegant design ensures maximum accuracy through primary paths while guaranteeing robustness and resilience through its fallback mechanisms.

