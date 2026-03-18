"""
Unified ICD provider with routing, fallback, and normalization.
"""
from __future__ import annotations

from logger import get_logger
from services.org_settings_service import get_org_settings
from services.icd_service import search_icd_by_text
from services.icd_response_mapper import normalize_icd10, normalize_icd11
from services.who_icd_service import search_icd as who_search_icd, enrich_with_local_flags

log = get_logger(__name__)


def _select_primary_system(settings: dict | None) -> str:
    claim_scheme = (settings or {}).get("claim_scheme")
    icd_version = (settings or {}).get("icd_version")

    if claim_scheme in {"ayushman", "cghs"}:
        return "ICD-11"
    if icd_version == "ICD-11":
        return "ICD-11"
    return "ICD-10"


async def get_icd_results(query: str, org_id: str, limit: int = 10) -> list[dict]:
    settings = await get_org_settings(org_id)
    primary_system = _select_primary_system(settings)
    fallback_used = False

    async def _icd10_search() -> list[dict]:
        return await search_icd_by_text(query, limit=limit)

    async def _icd11_search() -> list[dict]:
        results = await who_search_icd(query, icd_version="ICD-11", limit=limit)
        results = await enrich_with_local_flags(results)
        return results

    try:
        if primary_system == "ICD-11":
            primary_results = await _icd11_search()
            if not primary_results:
                fallback_used = True
                primary_results = await _icd10_search()
        else:
            primary_results = await _icd10_search()
            if not primary_results:
                fallback_used = True
                primary_results = await _icd11_search()
    except Exception as exc:
        log.error(
            "icd_provider_primary_failed",
            event="icd_provider_primary_failed",
            org_id=org_id,
            query=query,
            primary_system=primary_system,
            error=str(exc),
        )
        fallback_used = True
        primary_results = await _icd10_search()

    if primary_system == "ICD-11" and not fallback_used:
        normalized = normalize_icd11(_score_who(primary_results))
    elif primary_system == "ICD-10" and not fallback_used:
        normalized = normalize_icd10(primary_results)
    else:
        # fallback case — determine source from result shape
        normalized = _normalize_fallback(primary_results)

    log.info(
        "icd_provider_results",
        event="icd_provider_results",
        org_id=org_id,
        query=query,
        primary_system=primary_system,
        fallback_used=fallback_used,
        result_count=len(normalized),
    )

    return _sort_normalized(normalized, limit)


def _score_who(results: list[dict]) -> list[dict]:
    for r in results:
        mapping_type = r.get("mapping_type")
        if mapping_type == "who_autocode":
            r["score"] = 0.9
        else:
            r["score"] = 0.7
    return results


def _normalize_fallback(results: list[dict]) -> list[dict]:
    if not results:
        return []
    if results and results[0].get("icd_version") == "ICD-11":
        return normalize_icd11(_score_who(results))
    return normalize_icd10(results)


def _sort_normalized(results: list[dict], limit: int) -> list[dict]:
    results.sort(
        key=lambda r: (
            -(float(r.get("score") or 0.0)),
            len((r.get("description") or "")),
        )
    )
    return results[:limit]
