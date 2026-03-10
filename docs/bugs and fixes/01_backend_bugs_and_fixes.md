# Backend Bug Report & Fix Log
**Project:** Integronix — Revenue Integrity Platform  
**Review Date:** 2026-03-10  
**Reviewed By:** Senior Developer (AI Code Review)  
**Files Affected:** 8 backend files  
**Total Bugs Fixed:** 8 (1 Critical · 4 High · 3 Medium) + 1 Optimization  

---

## Table of Contents

1. [BUG-001 — Duplicate Node Registration (CRITICAL)](#bug-001)
2. [BUG-002 — Wrong Field Written to Database Column (HIGH)](#bug-002)
3. [BUG-003 — Missing Risk Category for Code Divergence (HIGH)](#bug-003)
4. [BUG-004 — Specificity Comparison Ignores ICD Category Prefix (HIGH)](#bug-004)
5. [BUG-005 — Wrong Discrepancy Label for Category Mismatch (HIGH)](#bug-005)
6. [BUG-006 — Database `limit` Parameter Passed Incorrectly (HIGH)](#bug-006)
7. [BUG-007 — `import json` Inside Function Body (MEDIUM)](#bug-007)
8. [BUG-008 — Silent Insert Failure on Database Error (MEDIUM)](#bug-008)
9. [REFACTOR-001 — Pydantic Schemas Living in Router File (MEDIUM)](#refactor-001)
10. [OPT-001 — Missing Groq API Key Validation Guard (OPTIMIZATION)](#opt-001)

---

## BUG-001 — Duplicate Node Registration {#bug-001}

| Field | Detail |
|---|---|
| **Severity** | 🔴 CRITICAL |
| **File** | `backend/agents/graph.py` |
| **Lines** | 87–88 |
| **Discovered** | Code Review |

### Description

The `build_integronix_graph()` function registered the `audit_comparison` and `risk_scoring` nodes **twice** with identical calls. This is a copy-paste error where lines 85–86 were duplicated on lines 87–88.

In LangGraph, calling `add_node()` twice with the same key either:
- Raises a `ValueError` and **crashes graph compilation** at startup (newer LangGraph versions), OR
- Silently **overwrites the node** with the same function (older versions), which is harmless functionally but signals a broken codebase

Either outcome is unacceptable. If this crashed compile, the entire pipeline would be dead on startup.

### Before (Broken)

```python
# agents/graph.py — lines 79–88
graph.add_node("doc_processing",   doc_processing_node)
graph.add_node("clinical_extract", clinical_extraction_agent)
graph.add_node("snomed_resolve",   snomed_resolver_node)
graph.add_node("snomed_icd_map",   snomed_icd_mapping_node)
graph.add_node("icd_embedding",    icd_embedding_node)
graph.add_node("icd_decision",     icd_decision_node)
graph.add_node("audit_comparison", audit_comparison_node)
graph.add_node("risk_scoring",     risk_scoring_node)
graph.add_node("audit_comparison", audit_comparison_node)   # ← DUPLICATE
graph.add_node("risk_scoring",     risk_scoring_node)       # ← DUPLICATE
```

### After (Fixed)

```python
# agents/graph.py — lines 79–86
graph.add_node("doc_processing",   doc_processing_node)
graph.add_node("clinical_extract", clinical_extraction_agent)
graph.add_node("snomed_resolve",   snomed_resolver_node)
graph.add_node("snomed_icd_map",   snomed_icd_mapping_node)
graph.add_node("icd_embedding",    icd_embedding_node)   # Fallback: vector search
graph.add_node("icd_decision",     icd_decision_node)    # Deterministic rule engine
graph.add_node("audit_comparison", audit_comparison_node)
graph.add_node("risk_scoring",     risk_scoring_node)
# ← removed the two duplicate lines that followed
```

### Root Cause

Copy-paste error during development. Lines 87–88 were accidentally left in after the original block was already written correctly above.

---

## BUG-002 — Wrong Field Written to Database Column {#bug-002}

| Field | Detail |
|---|---|
| **Severity** | 🟠 HIGH |
| **File** | `backend/agents/risk_scoring.py` |
| **Line** | 111 |
| **Discovered** | Code Review |

### Description

In the `risk_scoring_node`, when writing a row to the `coding_results` table, the `confidence_score` column was being populated with the `risk_score` value instead of the actual confidence score from the ICD decision node.

This means **every row ever written to `coding_results`** had its `confidence_score` and `risk_score` columns set to the same value — the risk score. The real confidence from the deterministic icd_decision engine (which carries clinical meaning — the weighted composite of specificity, clinical consistency, combination code priority) was silently discarded on every single pipeline run.

This is a data integrity bug with compliance implications — audit logs would show incorrect confidence values.

### Before (Broken)

```python
# agents/risk_scoring.py — line 111
await insert("coding_results", {
    ...
    "confidence_score": risk_score,     # ← BUG: stores risk_score in confidence_score column
    ...
    "risk_score":       risk_score,     # risk_score is now duplicated in both columns
    ...
})
```

### After (Fixed)

```python
# agents/risk_scoring.py — line 111
await insert("coding_results", {
    ...
    "confidence_score": state.get("confidence_score", 0.0),   # ← correct field from state
    ...
    "risk_score":       risk_score,
    ...
})
```

### Root Cause

Variable name confusion — `risk_score` was the most recently computed local variable, so it was accidentally reused for both columns. The `confidence_score` key available in `state` from `icd_decision_node` was overlooked.

---

## BUG-003 — Missing Risk Category for Code Divergence {#bug-003}

| Field | Detail |
|---|---|
| **Severity** | 🟠 HIGH |
| **File** | `backend/agents/risk_scoring.py` |
| **Line** | 18–24 |
| **Discovered** | Code Review (follow-on from BUG-005) |

### Description

The `DISCREPANCY_RISK` dictionary — which maps discrepancy types to a numeric risk weight — was missing the `CODE_DIVERGENCE` category that BUG-005 (below) introduced. Without this entry, any case with a code divergence would fall through to the `.get(discrepancy, 0.2)` default — assigning only 0.2 risk (same as `SPECIFICITY_IMPROVEMENT`) to a case where the AI and human coder picked codes from entirely different ICD-10 categories, which is actually the highest-stakes disagreement possible.

### Before (Broken)

```python
DISCREPANCY_RISK = {
    "EXACT_MATCH":              0.0,
    "NO_COMPARISON":            0.1,
    "SPECIFICITY_IMPROVEMENT":  0.2,
    "OVERCODING":               0.5,
    "UNSUPPORTED_CODE":         0.6,
    # CODE_DIVERGENCE missing — would default to 0.2 (same weight as SPECIFICITY_IMPROVEMENT)
}
```

### After (Fixed)

```python
DISCREPANCY_RISK = {
    "EXACT_MATCH":              0.0,
    "NO_COMPARISON":            0.1,
    "SPECIFICITY_IMPROVEMENT":  0.2,
    "CODE_DIVERGENCE":          0.45,  # Different ICD category — potential wrong code entirely
    "OVERCODING":               0.5,
    "UNSUPPORTED_CODE":         0.6,
}
```

### Why 0.45?

A `CODE_DIVERGENCE` case means the AI chose a code in a completely different clinical category than the human coder (e.g. pneumonia vs diabetes). This is more severe than a specificity mismatch (0.2) but the risk level sits just below actual overcoding (0.5) because the semantic divergence alone doesn't tell us which coder is wrong — it requires human review, not automatic rejection.

---

## BUG-004 — Specificity Comparison Ignores ICD Category Prefix {#bug-004}

| Field | Detail |
|---|---|
| **Severity** | 🟠 HIGH |
| **File** | `backend/agents/audit_comparison.py` |
| **Lines** | 14–20 |
| **Discovered** | Code Review |

### Description

The `_is_more_specific()` function determined specificity purely by code string length, without checking whether the two codes share the same ICD-10 category prefix.

In ICD-10-CM, code length correlates with specificity **only within the same category**:
- `E11.22` (Diabetes with diabetic CKD stage 2) is more specific than `E11.9` (Diabetes unspecified) ✅ — same `E11` category, longer = more detailed
- `E11.22` is **NOT** more specific than `J18.9` (Pneumonia) ❌ — completely different categories

The old code would evaluate `len("E11.22") > len("J18.9")` → `True`, and incorrectly classify a completely different diagnosis as a "specificity improvement". This caused the audit comparison to label cross-category disagreements as `SPECIFICITY_IMPROVEMENT` — the wrong audit type, wrong explanation, wrong financial framing.

### Before (Broken)

```python
def _is_more_specific(ai_code: str, human_code: str) -> bool:
    # A simple check to see if the AI's code is more specific.
    # In ICD-10, longer codes are generally more detailed (e.g., E11.22 vs. E11.9).
    if len(ai_code) > len(human_code):
        return True
    # TODO: Add more sophisticated logic here, like checking for complication keywords.
    return False
```

**Example failure case:**
- AI code: `E11.22` (length 6)
- Human code: `J18.9` (length 5)
- Result: `True` ← WRONG. These refer to completely different conditions.

### After (Fixed)

```python
def _is_more_specific(ai_code: str, human_code: str) -> bool:
    """
    Checks if ai_code is more specific than human_code.
    In ICD-10, a longer code = more detailed — BUT only within the same 3-character
    category prefix. E11.22 > E11.9 (same category, more specific). E11.22 is NOT
    more specific than J18.9 — they are different categories entirely.
    """
    # Different ICD-10 categories — cannot determine specificity by length
    if ai_code[:3] != human_code[:3]:
        return False
    return len(ai_code) > len(human_code)
```

**Example now:**
- `E11.22` vs `J18.9` → prefix `E11` ≠ `J18` → `False` (correctly routes to `CODE_DIVERGENCE`)
- `E11.22` vs `E11.9` → prefix `E11` == `E11` → `True` (correctly routes to `SPECIFICITY_IMPROVEMENT`)

### Root Cause

Incomplete ICD-10 code structure understanding in initial implementation. The TODO comment acknowledged this needed improvement — this fix implements the category prefix guard.

---

## BUG-005 — Wrong Discrepancy Label for Category Mismatch {#bug-005}

| Field | Detail |
|---|---|
| **Severity** | 🟠 HIGH |
| **File** | `backend/agents/audit_comparison.py` |
| **Lines** | 107–112 |
| **Discovered** | Code Review |

### Description

The `else` branch of the audit comparison — which fires when two codes differ, neither is more specific than the other, and the human code *is* valid in our DB — was labelling the result as `UNSUPPORTED_CODE`.

`UNSUPPORTED_CODE` has a specific meaning: the human code doesn't exist in ICD-10-CM-2024. Applying this label to a case where *both codes are valid* but in *different clinical categories* is factually incorrect. It would:

1. Mislead auditors into believing the human code is invalid (it's not)
2. Cause incorrect risk scoring (UNSUPPORTED_CODE weight is 0.6 — very high)
3. Generate inaccurate compliance reports and audit trails

The correct label for this situation is `CODE_DIVERGENCE` — both codes exist but they represent different clinical categories.

### Before (Broken)

```python
else:
    discrepancy_type = "UNSUPPORTED_CODE"    # ← WRONG: human code IS valid
    explanation = (
        f"Codes differ without clear specificity direction. "
        f"AI: '{ai_code}', Human: '{human_code}'. Review required."
    )
```

### After (Fixed)

```python
else:
    discrepancy_type = "CODE_DIVERGENCE"
    explanation = (
        f"AI code '{ai_code}' and human code '{human_code}' belong to different "
        f"ICD-10 categories — neither is a specificity improvement of the other. "
        f"This may indicate a fundamentally different clinical interpretation. "
        f"Manual review required.{drg_note}"
    )
```

### Root Cause

The `else` branch was a catch-all written before the `CODE_DIVERGENCE` concept was properly defined. The label `UNSUPPORTED_CODE` was reused incorrectly as a generic "something else went wrong" bucket.

---

## BUG-006 — Database `limit` Parameter Passed Incorrectly {#bug-006}

| Field | Detail |
|---|---|
| **Severity** | 🟠 HIGH |
| **File** | `backend/agents/snomed_resolver.py` (line 85) + `backend/database.py` (line 38) |
| **Discovered** | Code Review |

### Description

In `snomed_resolver.py`, the `limit` parameter for PostgREST queries was being passed **inside the `filters` dict** rather than as a proper query parameter. The `database.select()` function merged filters into the `params` dict which also already contained `select`, so the `limit` key *coincidentally* ended up in the right place in HTTP query params — but this was accidental behaviour, not intentional design.

More importantly, `database.select()` had **no explicit `limit` parameter** at all. This meant:
- Any caller wanting to limit results had to know the PostgREST-specific format (`"limit": "1"`) and embed it in the wrong abstraction layer (the filters dict)
- Static analysis and code review couldn't distinguish intentional filters from limit/offset controls
- Future refactoring of the DB layer could silently break limits across the entire codebase

### Before (Broken)

```python
# snomed_resolver.py — limit embedded in filters dict
rows = await select(
    table="snomed_concepts",
    query="snomed_code,description",
    filters={
        "description": f"ilike.*{phrase}*",
        "is_active":   "eq.true",
        "limit":       "1",       # ← wrong layer: this is a PostgREST detail, not a filter
    },
)

# database.py — select() had no limit param at all
async def select(table: str, query: str = "*", filters: dict | None = None) -> list[dict]:
    params = {"select": query}
    if filters:
        params.update(filters)   # limit sneaks in here incidentally
    ...
```

### After (Fixed)

```python
# database.py — explicit limit param added
async def select(
    table: str,
    query: str = "*",
    filters: dict | None = None,
    limit: int | None = None,     # ← proper, typed, first-class parameter
) -> list[dict]:
    params = {"select": query}
    if filters:
        params.update(filters)
    if limit is not None:
        params["limit"] = str(limit)   # applied at the DB layer, not the caller
    ...

# snomed_resolver.py — clean caller
rows = await select(
    table="snomed_concepts",
    query="snomed_code,description",
    filters={
        "description": f"ilike.*{phrase}*",
        "is_active":   "eq.true",
    },
    limit=1,   # ← clean, typed, explicit
)
```

### Root Cause

The initial `database.py` abstraction didn't anticipate the need for pagination controls. The `limit` key was added directly to filters as a workaround rather than extending the abstraction properly.

---

## BUG-007 — `import json` Inside Function Body {#bug-007}

| Field | Detail |
|---|---|
| **Severity** | 🟡 MEDIUM |
| **File** | `backend/database.py` |
| **Line** | 64 (original) |
| **Discovered** | Code Review |

### Description

The `import json` statement was placed inside the `insert()` function body rather than at the module top level. While Python caches imports so this carries no meaningful runtime performance penalty, it is considered bad practice because:

1. **Invisibility** — tools like `isort`, mypy, and IDE import analyzers don't see deferred imports
2. **Code smell** — suggests the import was added as an afterthought and not properly organised
3. **Static analysis failures** — some linters flag this as a code quality violation
4. **Team confusion** — other developers reading `database.py` won't know the module uses `json` without reading every function body

### Before (Broken)

```python
import httpx
from config import settings
...

async def insert(table: str, data: dict) -> dict | None:
    import json    # ← deferred import inside function
    client = await get_client()
    ...
    content=json.dumps(clean_data, default=str),
```

### After (Fixed)

```python
import json        # ← moved to top of file with other imports
import httpx
from config import settings
...

async def insert(table: str, data: dict) -> dict | None:
    client = await get_client()
    ...
    content=json.dumps(clean_data, default=str),   # json is now available
```

---

## BUG-008 — Silent Insert Failure on Database Error {#bug-008}

| Field | Detail |
|---|---|
| **Severity** | 🟡 MEDIUM |
| **File** | `backend/database.py` |
| **Lines** | 76–81 (original) |
| **Discovered** | Code Review |

### Description

When the `insert()` function received a non-200/201 HTTP response from Supabase, it logged a `warning` and **returned `None` silently**. Every caller in `risk_scoring.py` wrapped `insert()` calls in `try/except Exception` blocks — but since `insert()` swallowed the error and returned `None`, the `except` block never fired. The write failure was silently discarded.

This has compliance implications:

- **`audit_log` writes failing silently** means the audit trail has gaps — a HIPAA concern
- **`coding_results` writes failing silently** means billing data is lost without any alert
- **`clinical_cases` writes failing silently** means session data is lost

The callers in `risk_scoring.py` already have correct `try/except` error handling — they just needed `insert()` to actually raise, not swallow.

### Before (Broken)

```python
# database.py
if response.status_code in (200, 201):
    rows = response.json()
    return rows[0] if rows else None
log.warning(          # only a warning
    "insert_failed",
    table=table,
    status=response.status_code,
    detail=response.text[:200],
)
return None           # ← silently returns None, caller's except block never fires
```

```python
# risk_scoring.py — try/except is useless because insert() never raises
try:
    await insert("audit_log", { ... })
except Exception as e:
    log.warning("audit_log_write_failed", ...)   # ← this never executes on DB error
```

### After (Fixed)

```python
# database.py — raises on failure
if response.status_code in (200, 201):
    rows = response.json()
    return rows[0] if rows else None
detail = response.text[:300]
log.error(                # escalated to error
    "insert_failed",
    table=table,
    status=response.status_code,
    detail=detail,
)
raise DatabaseError(      # ← callers' except blocks now properly catch this
    f"Insert into '{table}' failed ({response.status_code}): {detail}",
    table=table,
    status=response.status_code,
)
```

```python
# risk_scoring.py — try/except now works correctly
try:
    await insert("audit_log", { ... })
except Exception as e:
    log.warning("audit_log_write_failed", ...)   # ← this now executes when DB fails
```

### Root Cause

The original design treated DB write failures as advisory — data loss was not considered a critical failure for the POC. In production, this must raise.

---

## REFACTOR-001 — Pydantic Schemas Living in Router File {#refactor-001}

| Field | Detail |
|---|---|
| **Severity** | 🟡 MEDIUM |
| **File** | `backend/routes/code.py` → `backend/models.py` |
| **Discovered** | Code Review |

### Description

`CodeRequest` and `CodeResponse` — the primary API request/response schemas for the main pipeline endpoint — were defined inline inside `routes/code.py`. All other Pydantic schemas (`DiagnosisEntity`, `ICDCode`, `AuditResult`, `CodingResult`, etc.) live in `models.py`. Having two of the most important schemas buried in the router file meant:

1. **Not testable in isolation** — you'd have to import the router to use these schemas
2. **Not reusable** — other routes or scripts couldn't import them without the router dependency chain
3. **Inconsistent architecture** — violated the established pattern of the rest of the codebase

### Fix

Moved `CodeRequest` and `CodeResponse` to `models.py` alongside all other schemas, and updated `routes/code.py` to import them:

```python
# routes/code.py — before
from pydantic import BaseModel
...
class CodeRequest(BaseModel): ...   # inline
class CodeResponse(BaseModel): ...  # inline

# routes/code.py — after
from models import CodeRequest, CodeResponse   # clean import
```

```python
# models.py — added
class CodeRequest(BaseModel):
    """Request body for POST /api/v1/code/run"""
    raw_text: str
    session_id: Optional[str] = None
    human_icd_code: Optional[str] = None

class CodeResponse(BaseModel):
    """Response from POST /api/v1/code/run"""
    ...
```

---

## OPT-001 — Missing Groq API Key Validation Guard {#opt-001}

| Field | Detail |
|---|---|
| **Severity** | 🔵 OPTIMIZATION |
| **File** | `backend/services/extraction_service.py` |
| **Lines** | 27–31 |
| **Discovered** | Code Review |

### Description

The Groq client factory `_get_groq_client()` created the `AsyncGroq` client unconditionally, even if `GROQ_API_KEY` was empty or missing. This would result in the client being created successfully, but then failing at the first API call with a cryptic Groq authentication error deep inside the pipeline — far from the root cause.

### Before

```python
def _get_groq_client() -> AsyncGroq:
    global _groq_client
    if _groq_client is None:
        _groq_client = AsyncGroq(api_key=settings.groq_api_key)  # ← no guard
    return _groq_client
```

Error developers would see: `AuthenticationError: No API key provided` — with a stack trace inside the Groq SDK, not at configuration.

### After (Fixed)

```python
def _get_groq_client() -> AsyncGroq:
    global _groq_client
    if _groq_client is None:
        if not settings.groq_api_key:
            raise ExtractionError(
                "GROQ_API_KEY is not configured — check your .env file",
                config_field="groq_api_key",
            )
        _groq_client = AsyncGroq(api_key=settings.groq_api_key)
    return _groq_client
```

Error developers now see: `ExtractionError: GROQ_API_KEY is not configured — check your .env file` — immediately actionable.

---

## Summary Table

| ID | Severity | File | Line(s) | Category | Fixed |
|---|---|---|---|---|---|
| BUG-001 | 🔴 Critical | `agents/graph.py` | 87–88 | Logic | ✅ |
| BUG-002 | 🟠 High | `agents/risk_scoring.py` | 111 | Data Integrity | ✅ |
| BUG-003 | 🟠 High | `agents/risk_scoring.py` | 18–24 | Logic | ✅ |
| BUG-004 | 🟠 High | `agents/audit_comparison.py` | 14–20 | Domain Logic | ✅ |
| BUG-005 | 🟠 High | `agents/audit_comparison.py` | 107–112 | Domain Logic | ✅ |
| BUG-006 | 🟠 High | `agents/snomed_resolver.py` + `database.py` | 77–90 + 38 | Abstraction | ✅ |
| BUG-007 | 🟡 Medium | `database.py` | 64 | Code Quality | ✅ |
| BUG-008 | 🟡 Medium | `database.py` | 76–81 | Error Handling | ✅ |
| REFACTOR-001 | 🟡 Medium | `routes/code.py` → `models.py` | 42–68 | Architecture | ✅ |
| OPT-001 | 🔵 Optimization | `services/extraction_service.py` | 27–31 | Developer UX | ✅ |

**All issues resolved. Python syntax check: 0 errors across all 8 modified files.**
