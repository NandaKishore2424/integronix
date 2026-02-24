import httpx
import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

_client: httpx.AsyncClient | None = None


def _headers(use_service_key: bool = False) -> dict:
    key = SUPABASE_SERVICE_KEY if use_service_key else SUPABASE_ANON_KEY
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


async def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            base_url=f"{SUPABASE_URL}/rest/v1",
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
