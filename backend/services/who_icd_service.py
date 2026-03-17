"""
services/who_icd_service.py — WHO ICD API Integration (v2)

Endpoints used (from WHO swagger at id.who.int/swagger/index.html):
  - GET /icd/entity/search     → multi-candidate search (Foundation)
  - GET /icd/entity/autocode   → single best-match for diagnostic text (Foundation)
  - GET /icd/release/11/{rel}/mms/search → MMS linearization search (has theCode)

ICD-11 primary path: MMS search → returns alphanumeric billing codes (5A11, etc.)
ICD-10 path:         Foundation autocode endpoint (universal)
Fallback:            Returns [] so embedding fallback in Node 5 kicks in

Auth: OAuth2 Client Credentials (cached, auto-refreshed)
"""
import time
import asyncio
import re
import httpx

from config import settings
from logger import get_logger
from database import upsert_icd_code_from_who

log = get_logger(__name__)

# ── Token Cache ───────────────────────────────────────────────────────────────

_token_lock = asyncio.Lock()
_token_cache: dict = {"token": None, "expires_at": 0.0}


async def _get_access_token() -> str:
    """
    Fetches + caches OAuth2 Bearer token from WHO Access Management.
    Auto-refreshes 60 seconds before expiry. Thread-safe via asyncio.Lock.
    """
    async with _token_lock:
        now = time.time()
        if _token_cache["token"] and now < _token_cache["expires_at"] - 60:
            return _token_cache["token"]

        log.info("who_icd_token_refresh", reason="expired_or_missing")
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                settings.who_icd_token_endpoint,
                data={
                    "grant_type":    "client_credentials",
                    "client_id":     settings.who_icd_client_id,
                    "client_secret": settings.who_icd_client_secret,
                    "scope":         "icdapi_access",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            data = resp.json()

        _token_cache["token"]      = data["access_token"]
        _token_cache["expires_at"] = now + int(data.get("expires_in", 3600))
        log.info("who_icd_token_acquired", expires_in=data.get("expires_in"))
        return _token_cache["token"]


def _headers(token: str) -> dict:
    """Required headers for all WHO ICD API v2 calls."""
    return {
        "Authorization":   f"Bearer {token}",
        "Accept":          "application/json",
        "Accept-Language": "en",
        "API-Version":     "v2",
    }


def _strip_html(text: str) -> str:
    """Remove HTML tags that WHO API sometimes includes in titles."""
    return re.sub(r"<[^>]+>", "", text).strip()


# ── Core Search ───────────────────────────────────────────────────────────────

async def search_icd(
    query: str,
    icd_version: str = "ICD-11",
    limit: int = 10,
) -> list[dict]:
    """
    Search WHO ICD API for clinical text. Returns normalised candidate list.

    ICD-11: Uses MMS linearization search → returns alphanumeric billing codes
    ICD-10: Uses Foundation autocode → returns best match, then entity search

    Returns [] on any error so the embedding fallback in Node 5 engages.
    """
    if not settings.who_icd_client_id or not settings.who_icd_client_secret:
        log.warning("who_icd_search_skipped", reason="credentials_not_configured")
        return []
    if not query or not query.strip():
        return []

    try:
        token   = await _get_access_token()
        headers = _headers(token)

        if icd_version == "ICD-11":
            results = await _search_icd11_mms(query, headers, limit)
        else:
            # ICD-10: use autocode endpoint (Foundation works across versions)
            results = await _autocode_foundation(query, headers)
            if not results:
                results = await _search_foundation(query, headers, limit)

        log.info(
            "who_icd_search_complete",
            query=query[:70],
            version=icd_version,
            results_found=len(results),
        )

        # ── Background cache: persist new codes to local icd_codes table ──────
        # Fire-and-forget: creates background tasks so zero latency added to user
        for r in results:
            if r.get("code") and r.get("description"):
                asyncio.create_task(
                    upsert_icd_code_from_who(
                        code=r["code"],
                        description=r["description"],
                        icd_version=r.get("icd_version", icd_version),
                    )
                )

        return results

    except httpx.TimeoutException:
        log.warning("who_icd_search_timeout", query=query[:60])
        return []
    except Exception as exc:
        log.error("who_icd_search_failed", error=str(exc), query=query[:60])
        return []


# ── ICD-11 MMS Linearization Search ──────────────────────────────────────────

async def _search_icd11_mms(query: str, headers: dict, limit: int) -> list[dict]:
    """
    GET /icd/release/11/{releaseId}/mms/search
    MMS = Mortality and Morbidity Statistics linearization.
    Returns actual ICD-11 billing codes (e.g. 5A11, BA00, etc.)
    """
    url = (
        f"{settings.who_icd_api_base}/icd/release/11"
        f"/{settings.who_icd_11_release}/mms/search"
    )
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            url,
            params={
                "q":                 query.strip(),
                "flatResults":       "true",
                "useFlexisearch":    "false",     # strict first
                "highlightingEnabled": "false",
            },
            headers=headers,
        )

    if resp.status_code != 200:
        log.warning("who_icd_mms_search_error", status=resp.status_code, url=url)
        # Try with flexisearch as fallback
        return await _search_icd11_mms_flexible(query, headers, limit)

    data     = resp.json()
    entities = data.get("destinationEntities", [])

    results = []
    for entity in entities[:limit]:
        code = entity.get("theCode", "")
        if not code:
            continue
        results.append(_normalise_entity(entity, "ICD-11"))

    # If strict search returned nothing, try flexible
    if not results:
        return await _search_icd11_mms_flexible(query, headers, limit)

    return results


async def _search_icd11_mms_flexible(query: str, headers: dict, limit: int) -> list[dict]:
    """Retry MMS search with useFlexisearch=true for broader matching."""
    url = (
        f"{settings.who_icd_api_base}/icd/release/11"
        f"/{settings.who_icd_11_release}/mms/search"
    )
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            url,
            params={
                "q":                   query.strip(),
                "flatResults":         "true",
                "useFlexisearch":      "true",
                "highlightingEnabled": "false",
            },
            headers=headers,
        )

    if resp.status_code != 200:
        log.warning("who_icd_mms_flex_error", status=resp.status_code)
        return []

    data    = resp.json()
    results = []
    for entity in data.get("destinationEntities", [])[:limit]:
        code = entity.get("theCode", "")
        if not code:
            continue
        results.append(_normalise_entity(entity, "ICD-11"))
    return results


# ── Foundation Autocode (best single match) ───────────────────────────────────

async def _autocode_foundation(query: str, headers: dict) -> list[dict]:
    """
    GET /icd/entity/autocode?searchText={query}
    Returns single best-matching entity from ICD-11 Foundation.
    Used as primary path for ICD-10 requests (Foundation is version-agnostic).
    """
    url = f"{settings.who_icd_api_base}/icd/entity/autocode"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            url,
            params={"searchText": query.strip()},
            headers=headers,
        )

    if resp.status_code != 200:
        log.warning("who_icd_autocode_error", status=resp.status_code)
        return []

    data = resp.json()
    # Autocode returns a single entity, not a list
    entity_id  = data.get("id", "")
    title      = _strip_html(data.get("title", ""))
    code       = data.get("theCode") or entity_id.split("/")[-1]

    if not code or not title:
        return []

    return [{
        "code":         code,
        "description":  title,
        "score":        1.0,       # Autocode returns best match, score = confident
        "is_cc":        False,
        "is_mcc":       False,
        "is_billable":  True,
        "icd_version":  "ICD-11",  # Foundation maps to ICD-11
        "mapping_type": "who_autocode",
        "source":       "who_icd_api",
    }]


# ── Foundation Entity Search (multi-candidate) ────────────────────────────────

async def _search_foundation(query: str, headers: dict, limit: int) -> list[dict]:
    """
    GET /icd/entity/search?q={query}
    Searches ICD-11 Foundation component. Returns multiple candidates.
    """
    url = f"{settings.who_icd_api_base}/icd/entity/search"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            url,
            params={
                "q":                   query.strip(),
                "flatResults":         "true",
                "useFlexisearch":      "true",
                "highlightingEnabled": "false",
            },
            headers=headers,
        )

    if resp.status_code != 200:
        log.warning("who_icd_foundation_search_error", status=resp.status_code)
        return []

    results = []
    for entity in resp.json().get("destinationEntities", [])[:limit]:
        code = entity.get("theCode") or entity.get("id", "").split("/")[-1]
        if not code:
            continue
        results.append(_normalise_entity(entity, "ICD-11"))
    return results


# ── Normalise ─────────────────────────────────────────────────────────────────

def _normalise_entity(entity: dict, version: str) -> dict:
    """Convert a WHO API entity dict into our internal candidate format."""
    code  = entity.get("theCode", "") or entity.get("id", "").split("/")[-1]
    title = _strip_html(entity.get("title", ""))
    score = float(entity.get("score") or 0.0)
    return {
        "code":         code,
        "description":  title,
        "score":        round(score, 4),
        "is_cc":        False,    # Enriched from local cache later
        "is_mcc":       False,
        "is_billable":  True,
        "icd_version":  version,
        "mapping_type": "who_api_search",
        "source":       "who_icd_api",
    }


# ── CC/MCC Enrichment from local cache ────────────────────────────────────────

async def enrich_with_local_flags(results: list[dict]) -> list[dict]:
    """
    Look up CC/MCC flags and base_reimbursement from the local icd_codes table.
    Lazy import to avoid circular imports at module load time.
    """
    if not results:
        return results
    from database import select_one
    for r in results:
        local = await select_one(
            table="icd_codes",
            query="is_cc,is_mcc,base_reimbursement",
            filters={"code": f"eq.{r['code']}"},
        )
        if local:
            r["is_cc"]             = local.get("is_cc", False)
            r["is_mcc"]            = local.get("is_mcc", False)
            r["base_reimbursement"] = float(local.get("base_reimbursement", 5000.0))
        else:
            r["base_reimbursement"] = 5000.0  # Default until DB cache is warm
    return results
