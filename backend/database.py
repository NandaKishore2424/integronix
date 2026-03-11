import json
import httpx
from config import settings
from exceptions import DatabaseError
from logger import get_logger

log = get_logger(__name__)

_client: httpx.AsyncClient | None = None


def _headers() -> dict:
    key = settings.supabase_service_key or settings.supabase_anon_key
    return {
        "apikey": settings.supabase_anon_key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


async def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            base_url=f"{settings.supabase_url}/rest/v1",
            headers=_headers(),
            timeout=10.0,
        )
    return _client


async def close_client():
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None


async def select(
    table: str,
    query: str = "*",
    filters: dict | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Perform a SELECT query via Supabase PostgREST."""
    client = await get_client()
    params = {"select": query}
    if filters:
        params.update(filters)
    if limit is not None:
        params["limit"] = str(limit)
    response = await client.get(f"/{table}", params=params)
    response.raise_for_status()
    return response.json()


async def select_one(table: str, query: str = "*", filters: dict | None = None) -> dict | None:
    rows = await select(table, query, filters)
    return rows[0] if rows else None


async def rpc(function_name: str, params: dict) -> list[dict] | dict:
    """Call a Supabase RPC function (for vector similarity search)."""
    client = await get_client()
    response = await client.post(f"/rpc/{function_name}", json=params)
    response.raise_for_status()
    return response.json()


async def insert(table: str, data: dict) -> dict | None:
    """Insert a row into a Supabase table via PostgREST. Returns inserted row."""
    client = await get_client()
    # Remove None values — let DB defaults handle them
    clean_data = {k: v for k, v in data.items() if v is not None}
    response = await client.post(
        f"/{table}",
        content=json.dumps(clean_data, default=str),
        headers={**_headers(), "Prefer": "return=representation"},
    )
    if response.status_code in (200, 201):
        rows = response.json()
        return rows[0] if rows else None
    # Raise so callers (audit_log, coding_results) can handle or log appropriately
    detail = response.text[:300]
    log.error(
        "insert_failed",
        table=table,
        status=response.status_code,
        detail=detail,
    )
    raise DatabaseError(
        f"Insert into '{table}' failed ({response.status_code}): {detail}",
        table=table,
        status=response.status_code,
    )
async def select_paginated(
    table: str,
    query: str = "*",
    filters: dict | None = None,
    order: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    """
    Paginated SELECT using PostgREST Range header.
    Returns (rows, total_count).
    """
    client = await get_client()
    params: dict = {"select": query}
    if filters:
        params.update(filters)
    if order:
        params["order"] = order

    offset = (page - 1) * page_size
    range_header = f"{offset}-{offset + page_size - 1}"

    response = await client.get(
        f"/{table}",
        params=params,
        headers={
            **_headers(),
            "Range": range_header,
            "Range-Unit": "items",
            "Prefer": "count=exact",
        },
    )
    response.raise_for_status()

    # PostgREST returns total in Content-Range: 0-19/47
    content_range = response.headers.get("Content-Range", "")  # e.g. "0-19/47"
    total = 0
    if "/" in content_range:
        try:
            total = int(content_range.split("/")[-1])
        except ValueError:
            pass

    return response.json(), total


async def select_count(table: str, filters: dict | None = None) -> int:
    """Return the total count of rows matching the given filters."""
    client = await get_client()
    params: dict = {"select": "count"}
    if filters:
        params.update(filters)
    response = await client.get(
        f"/{table}",
        params=params,
        headers={**_headers(), "Prefer": "count=exact"},
    )
    response.raise_for_status()
    content_range = response.headers.get("Content-Range", "")
    if "/" in content_range:
        try:
            return int(content_range.split("/")[-1])
        except ValueError:
            pass
    return 0
