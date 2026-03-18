# Product & Engineering Review (March 2026)

This document records a **rigid, production‑grade review** of the Integronix codebase. It is **not** a deployment review. It focuses on **development quality, architecture, domain correctness, client readiness, and UI integrity**.

Each item includes:
- **Simple explanation** (non‑technical)
- **Technical explanation**
- **What could go wrong**
- **Recommended fix**
- **How to verify**

Items are ordered by **priority** (Critical → High → Medium → Low).

---

## 🔴 P0 — Critical (must fix before any serious pilot)

### 1) Risk scoring can crash on error
**Simple:** If anything goes wrong while calculating risk, the pipeline can crash instead of returning a safe score.

**Technical:** `_compute_risk()` in `risk_scoring.py` catches exceptions but does **not** return a `(score, label)` tuple in the exception path. The caller unpacks the return value, which can become `None`, causing a runtime error.

**What could go wrong:** Requests intermittently fail with 500s. Cases are not saved. Users see missing results.

**Fix:** Always return a safe default tuple from `_compute_risk()` in all paths.

**How to verify:**
1. Add a test that forces a fault inside `_compute_risk()`.
2. Ensure the response still returns valid `risk_score` and `risk_label`.

---

### 2) FHIR output always uses ICD‑10 system
**Simple:** Even when ICD‑11 is used, the output still claims ICD‑10, which is wrong clinically and legally.

**Technical:** `_build_fhir_condition()` in `routes/code.py` always sets coding system to `icd-10-cm`, regardless of routing. This is incorrect for ICD‑11 outputs.

**What could go wrong:** Incorrect coding system in exported FHIR leads to claim rejection or compliance issues.

**Fix:** Dynamically set FHIR coding system and version based on `icd_version` or candidate metadata.

**How to verify:**
1. Force ICD‑11 routing.
2. Check FHIR `code.coding.system` is ICD‑11 compatible.

---

### 3) Schema drift vs writes in `coding_results`
**Simple:** The backend writes fields that may not exist in the database, so data can silently fail to save.

**Technical:** `risk_scoring` inserts `icd_codes_full` and `drg_flag` into `coding_results`. These fields are not present in the documented schema.

**What could go wrong:** Missing fields in analytics, silent insert errors, and broken dashboards.

**Fix:** Align DB schema with writes (add fields) OR remove fields from write payload.

**How to verify:**
1. Run a real pipeline request.
2. Confirm `coding_results` includes all expected fields with no DB warnings.

---

### 4) Audit evidence table referenced but not defined
**Simple:** Audit explanations say “no evidence available” even when evidence should exist.

**Technical:** `audit_comparison` fetches from `icd_evidence` table which is not declared in schema docs. That query usually returns nothing.

**What could go wrong:** Audit credibility is damaged; reviewers see empty evidence trails.

**Fix:** Either create the `icd_evidence` table and seed it, or remove the lookup and rely on extraction evidence.

**How to verify:**
1. Run audit comparison.
2. Verify evidence snippet is present and meaningful.

---

## 🟠 P1 — High Priority (stability + scale risks)

### 5) Async pipeline uses blocking DB calls
**Simple:** Some steps block the whole server even though everything is async.

**Technical:** `financial_calculator` and `cpt_resolver` call the synchronous Supabase client inside async nodes. This blocks the event loop under load.

**What could go wrong:** Severe slowdown as concurrency increases; requests timeout.

**Fix:** Use async client or run blocking work in thread executor.

**How to verify:**
1. Load test with 20+ concurrent requests.
2. Check latency distribution and CPU usage.

---

### 6) Frontend response type is outdated
**Simple:** The UI doesn’t fully understand the backend’s latest response.

**Technical:** `frontend/src/types/coding.ts` doesn’t include `decision_trace` or extended `mapping_path` values; ICD‑11 cases aren’t fully typed.

**What could go wrong:** UI breaks when rendering new fields, or silently ignores them.

**Fix:** Update types and UI mappings to handle new response shape.

**How to verify:**
1. Run ICD‑11 route.
2. Confirm UI displays mapping path and decision trace.

---

### 7) WHO API client is created per call
**Simple:** WHO API calls are slower than they need to be.

**Technical:** `who_icd_service` uses new `httpx.AsyncClient()` per request, losing connection pooling.

**What could go wrong:** Higher latency and API cost, increased failure rate under load.

**Fix:** Reuse a global `AsyncClient` with proper shutdown on app close.

**How to verify:**
1. Benchmark with 100 WHO calls.
2. Confirm latency improves and connection reuse occurs.

---

## 🟡 P2 — Medium Priority (quality + correctness)

### 8) ICD‑11 vs ICD‑10 candidate mixing risk
**Simple:** Candidates from different systems can appear together, which confuses the decision engine.

**Technical:** Provider augmentation can inject ICD‑11 results into a pipeline that already has ICD‑10 candidates, unless explicitly filtered.

**What could go wrong:** Wrong code system chosen, inconsistent output.

**Fix:** Enforce single‑system candidate lists based on `icd_version` at decision time.

**How to verify:**
1. Force ICD‑10 routing and inject WHO fallback.
2. Confirm all candidates belong to ICD‑10.

---

### 9) Evidence extraction is too naive
**Simple:** Evidence snippets can be wrong or empty.

**Technical:** Evidence snippet is extracted by simple string search; it fails for paraphrased evidence and can return unrelated fragments.

**What could go wrong:** Auditors reject results due to weak citations.

**Fix:** Use semantic sentence matching or anchor to LLM‑extracted evidence field.

**How to verify:**
1. Use a document where diagnosis is paraphrased.
2. Ensure evidence is still accurate.

---

### 10) CPT model loaded at import time
**Simple:** Cold start is heavier than necessary.

**Technical:** `cpt_resolver` loads sentence‑transformer at import time, which slows startup.

**What could go wrong:** Slow cold starts in serverless or container environments.

**Fix:** Lazy‑load CPT embedding model like ICD embedding node.

**How to verify:**
1. Measure cold‑start time before/after change.

---

## 🟢 P3 — Low Priority (polish + clarity)

### 11) CORS is hard‑coded for localhost
**Simple:** Frontend in production won’t be able to call the backend unless changed manually.

**Technical:** CORS origins are hard‑coded in `main.py`.

**Fix:** Move allowed origins to config/env and load per environment.

**How to verify:**
1. Run with a production domain value.
2. Confirm requests succeed.

---

### 12) Default reimbursement values may mislead
**Simple:** WHO API cached codes get a default reimbursement value that might be wrong.

**Technical:** `upsert_icd_code_from_who` inserts `base_reimbursement=5000` by default.

**What could go wrong:** Financial delta calculations are misleading for ICD‑11 cases.

**Fix:** Use null for unknown reimbursement or separate payer‑specific lookup table.

**How to verify:**
1. Load WHO code.
2. Confirm reimbursement is only filled when real mapping exists.

---

# Client‑Facing / Domain Recommendations

## A) Clinical correctness
- Always output the correct ICD system in FHIR.
- Avoid mixing ICD‑10 and ICD‑11 candidate sets.
- Ensure evidence citations are defensible (required for auditor trust).

## B) Trust & explainability
- `decision_trace` should be surfaced in UI for auditors.
- Store decision trace in `audit_log` for post‑hoc review.

## C) Business readiness
- Add a validation harness for coding accuracy (top‑1, top‑3, top‑5).
- Make payer rules and reimbursement logic optional but explicit.

---

# UI & Client Experience Gaps

1. **Decision trace not shown** — product loses “explainable AI” promise.
2. **ICD‑11 not clearly marked** — users may assume ICD‑10 output.
3. **Audit evidence field weak** — reviewers will demand stronger evidence.

---

# Next Action Plan (Suggested Order)

1) Fix risk scoring return path
2) Fix FHIR coding system by ICD version
3) Align database schema with writes
4) Resolve `icd_evidence` table mismatch
5) Remove blocking DB calls in async nodes
6) Update frontend response types
7) Enforce single ICD system candidate lists
8) Improve evidence extraction
9) Lazy‑load CPT embedding model
10) Config‑driven CORS

---

## Acceptance Checks (Quick)
- No 500s on `risk_scoring`.
- ICD‑11 response produces ICD‑11 FHIR coding.
- DB inserts succeed without warnings.
- Frontend renders all response fields.
- Evidence snippets are meaningful.

---

**Owner:** Product Engineering
**Status:** Draft review, not yet applied
