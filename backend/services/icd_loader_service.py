"""
ICD-10-CM bulk loaders (DB-only logic). Uses Supabase PostgREST client.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Iterable, Sequence

from config import settings
from logger import get_logger
from database import get_client

log = get_logger(__name__)

DEFAULT_BATCH_SIZE = 500


def _chunked(data: Sequence[dict], batch_size: int) -> Iterable[list[dict]]:
    for i in range(0, len(data), batch_size):
        yield data[i : i + batch_size]


def _headers() -> dict:
    key = settings.supabase_service_key or settings.supabase_anon_key
    return {
        "apikey": settings.supabase_anon_key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=ignore-duplicates,return=minimal",
    }


async def bulk_insert_icd_codes(data: Sequence[dict], batch_size: int = DEFAULT_BATCH_SIZE) -> int:
    client = await get_client()
    inserted = 0
    for batch in _chunked(list(data), batch_size):
        resp = await client.post(
            "/icd_codes",
            json=batch,
            headers=_headers(),
            params={"on_conflict": "code"},
        )
        if resp.status_code in (200, 201, 204):
            inserted += len(batch)
        else:
            log.error("icd_codes_insert_failed", status=resp.status_code, detail=resp.text[:300])
    log.info("icd_codes_insert_complete", rows=inserted)
    return inserted


async def bulk_insert_hierarchy(data: Sequence[dict], batch_size: int = DEFAULT_BATCH_SIZE) -> int:
    client = await get_client()
    inserted = 0
    for batch in _chunked(list(data), batch_size):
        resp = await client.post(
            "/icd_code_hierarchy",
            json=batch,
            headers=_headers(),
            params={"on_conflict": "code"},
        )
        if resp.status_code in (200, 201, 204):
            inserted += len(batch)
        else:
            log.error("icd_hierarchy_insert_failed", status=resp.status_code, detail=resp.text[:300])
    log.info("icd_hierarchy_insert_complete", rows=inserted)
    return inserted


async def bulk_insert_metadata(data: Sequence[dict], batch_size: int = DEFAULT_BATCH_SIZE) -> int:
    client = await get_client()
    inserted = 0
    for batch in _chunked(list(data), batch_size):
        resp = await client.post(
            "/icd_code_metadata",
            json=batch,
            headers=_headers(),
            params={"on_conflict": "code"},
        )
        if resp.status_code in (200, 201, 204):
            inserted += len(batch)
        else:
            log.error("icd_metadata_insert_failed", status=resp.status_code, detail=resp.text[:300])
    log.info("icd_metadata_insert_complete", rows=inserted)
    return inserted


async def bulk_insert_index_terms(data: Sequence[dict], batch_size: int = DEFAULT_BATCH_SIZE) -> int:
    """
    Insert index terms in batches.
    NOTE: Deduplication strategy is prepared but not applied yet.
    """
    client = await get_client()
    inserted = 0
    for batch in _chunked(list(data), batch_size):
        resp = await client.post(
            "/icd_index_terms",
            json=batch,
            headers=_headers(),
        )
        if resp.status_code in (200, 201, 204):
            inserted += len(batch)
        else:
            log.error("icd_index_insert_failed", status=resp.status_code, detail=resp.text[:300])
    log.info("icd_index_insert_complete", rows=inserted)
    return inserted


def dataclass_rows_to_dicts(rows: Sequence[object]) -> list[dict]:
    return [asdict(r) for r in rows]
