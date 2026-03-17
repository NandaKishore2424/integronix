# ICD API Integration — Technical Reference & Implementation

> **Status:** ✅ Phase 1 Complete — Live WHO ICD API integrated and verified  
> **Verified:** 2026-03-12 — ICD-11 MMS search returning real codes  
> **API Version:** v2 (required header: `API-Version: v2`)  
> **Base URL:** `https://id.who.int`

---

## Overview

Integronix uses the **WHO ICD API v2** to perform clinical text → ICD code resolution.  
This replaces the previous static SNOMED lookup (17 concepts) + hand-coded crosswalk (11 entries) with WHO's full live classification covering 70,000+ entities.

**Primary classification:** ICD-11 (MMS linearization — required for Ayushman Bharat / ABDM mandate)  
**Secondary classification:** ICD-10 (available per hospital via `org_settings.icd_version`)

---

## Where It Fits in the Pipeline

```
Node 2 (Groq LLM) → extracts diagnosis text
        │
        ▼
Node 3 [snomed_resolver.py] — NOW CALLS WHO ICD API
    ├── Primary:  WHO ICD API MMS search → ICD-11 codes → candidate_icd_codes[]
    ├── Fallback: WHO ICD API Foundation search (if MMS returns 0)
    └── Last:     Old SNOMED DB lookup (if WHO API down/returns 0)
        │
        ▼
Node 4 [snomed_icd_mapper.py]
    └── SKIPS entirely if WHO API already populated candidates
        │
        ▼
Node 5 [icd_embedding.py]
    └── SKIPS if candidates present, runs only as last fallback
        │
        ▼
Node 6 (Decision Engine) → picks winner from candidates
```

---

## Authentication

**Method:** OAuth2 Client Credentials Flow  
**Token endpoint:** `https://icdaccessmanagement.who.int/connect/token`

```python
# POST request
data = {
    "grant_type":    "client_credentials",
    "client_id":     WHO_ICD_CLIENT_ID,
    "client_secret": WHO_ICD_CLIENT_SECRET,
    "scope":         "icdapi_access",
}
# Returns: {"access_token": "...", "expires_in": 3600}
```

**Token caching:** Token is cached in-process and auto-refreshed 60 seconds before expiry.  
`services/who_icd_service.py` — `_get_access_token()` — thread-safe via `asyncio.Lock`.

### Required Headers (every call)
```
Authorization:   Bearer <token>
Accept:          application/json
Accept-Language: en
API-Version:     v2
```

---

## Endpoints Used

### 1. ICD-11 MMS Search (Primary — for billing codes)
```
GET /icd/release/11/{releaseId}/mms/search
```

| Parameter | Value | Notes |
|---|---|---|
| `q` | clinical text | e.g. "Type 2 diabetes with CKD stage 3" |
| `flatResults` | `true` | Returns flat list, not nested hierarchy |
| `useFlexisearch` | `false` first, `true` on retry | Strict match first, fuzzy if 0 results |
| `highlightingEnabled` | `false` | Removes `<em>` HTML tags from titles |

**Current release ID:** `2026-01` (config: `who_icd_11_release`)  
**Important:** Release ID format is `YYYY-MM` (e.g. `2024-01`, `2026-01`). Using just `"2026"` returns 0 results.

**Response structure:**
```json
{
  "destinationEntities": [
    {
      "theCode": "5A11",
      "title":   "Type 2 diabetes mellitus",
      "score":   0.9432,
      "id":      "http://id.who.int/icd/release/11/2026-01/mms/5A11"
    }
  ]
}
```

**Note:** `theCode` is the ICD-11 alphanumeric billing code (e.g. `5A11`, `BA00`, `1C62`).  
Entities without `theCode` are skipped (they are grouper entities, not billable).

---

### 2. Foundation Entity Search (Multi-candidate fallback)
```
GET /icd/entity/search
```

| Parameter | Value |
|---|---|
| `q` | clinical text |
| `flatResults` | `true` |
| `useFlexisearch` | `true` |
| `highlightingEnabled` | `false` |

No release ID needed — Foundation is version-agnostic.  
Returns entity numeric IDs from Foundation (`1697306310` etc.) — used only as fallback.

---

### 3. Foundation Autocode (Best single match)
```
GET /icd/entity/autocode?searchText={query}
```

Returns single best-matching entity. Used for ICD-10 mode fallback.  
**Note:** `theCode` may be `null` for some Foundation entities — handle gracefully.

---

### 4. Foundation Entity Lookup (by ID)
```
GET /icd/entity/{id}
```

Fetches details of a specific entity by its numeric Foundation ID.  
Used to resolve entity details after a search returns an ID.

---

## Org-Level Configuration (`org_settings` table)

Each hospital can request different classification via the `org_settings` table:

```sql
-- Run migration 019_org_settings.sql in Supabase first
SELECT icd_version FROM org_settings WHERE organization_id = $1;
```

| `icd_version` | WHO API Endpoint Used | Use Case |
|---|---|---|
| `ICD-11` (default) | MMS linearization `/release/11/2026-01/mms/search` | Ayushman Bharat, CGHS, ABDM |
| `ICD-10` | Foundation autocode + search | Private insurers in transition |

The value is read by the code route (`routes/code.py`) and passed into LangGraph state as `icd_version`.  
`snomed_resolver.py` reads `state["icd_version"]` to select the endpoint.

---

## Environment Variables

```bash
# backend/.env
WHO_ICD_CLIENT_ID=<your_client_id>
WHO_ICD_CLIENT_SECRET=<your_client_secret>
WHO_ICD_TOKEN_ENDPOINT=https://icdaccessmanagement.who.int/connect/token
WHO_ICD_API_BASE=https://id.who.int
```

```python
# backend/config.py (Settings class)
who_icd_client_id:       str = ""
who_icd_client_secret:   str = ""
who_icd_token_endpoint:  str = "https://icdaccessmanagement.who.int/connect/token"
who_icd_api_base:        str = "https://id.who.int"
who_icd_default_version: str = "ICD-11"
who_icd_11_release:      str = "2026-01"   # MUST be YYYY-MM format
who_icd_10_release:      str = "2019"
```

---

## Key Files

| File | Role |
|---|---|
| `backend/services/who_icd_service.py` | WHO API client — auth, search, response normalisation |
| `backend/agents/snomed_resolver.py` | Node 3 — calls WHO API, falls back to SNOMED DB |
| `backend/agents/snomed_icd_mapper.py` | Node 4 — skips when WHO API populated candidates |
| `backend/routes/code.py` | Injects `icd_version` from config into pipeline state |
| `backend/config.py` | WHO API settings (credentials, release IDs) |
| `backend/.env` | Actual credential values (not committed to git) |
| `migrations/019_org_settings.sql` | Creates per-org ICD version config table |

---

## Verification (Confirmed Working — 2026-03-12)

```
TEST 1: ICD-11 MMS search — diabetes + CKD
SUCCESS: 3 ICD-11 candidates
  [5A11] Type 2 diabetes mellitus, unspecified
  ...

TEST 2: ICD-11 — heart failure
SUCCESS: 3 results

TEST 3: ICD-11 — hypertension  
SUCCESS: 3 results
```

---

## Known Limitations & Notes

| Item | Detail |
|---|---|
| ICD-10 via WHO API | Foundation autocode returns limited ICD-10-specific detail. For full ICD-10 matching, local embedding fallback engages. |
| WHO API rate limits | No documented rate limit on free tier. Token is valid 3600s. Cache it — don't re-fetch. |
| Billable vs grouper codes | MMS search only. Foundation entities without `theCode` are skipped — they're hierarchy groupers not billable codes. |
| CC/MCC flags | Not in WHO API response — enriched from local `icd_codes` table cache after search. |
| Revenue data | Not in WHO API — `base_reimbursement` from local `icd_codes` table (DRG rates are payer-specific). |
| Local deployment | WHO API can run as Docker container for air-gapped hospital environments. See Phase 5 of hosting plan. |

---

## WHO ICD API — Useful Links

| Resource | URL |
|---|---|
| API Home | https://icd.who.int/icdapi |
| Swagger (try endpoints live) | https://id.who.int/swagger/index.html |
| Supported Classifications (release IDs) | https://icd.who.int/docs/icd-api/SupportedClassifications/ |
| Authentication Guide | https://icd.who.int/docs/icd-api/APIDoc-Version2/ |
| ICD-11 Reference | https://icd.who.int/browse/2026-01/mms/en |
| Release Notes v2.6 | https://icd.who.int/docs/icd-api/ReleaseNotes-Version2.6/ |
