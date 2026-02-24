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


async def select(table: str, query: str = "*", filters: dict | None = None) -> list[dict]:
    """Perform a SELECT query via Supabase PostgREST."""
    client = await get_client()
    params = {"select": query}
    if filters:
        params.update(filters)
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
    import json
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
    log.warning(
        "insert_failed",
        table=table,
        status=response.status_code,
        detail=response.text[:200],
    )
    return None
