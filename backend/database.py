import json
import httpx
from config import settings
from exceptions import DatabaseError
from logger import get_logger

log = get_logger(__name__)

_client: httpx.AsyncClient | None = None
_client_loop_id: int | None = None


def _headers(user_token: str | None = None) -> dict:
    """
    Build PostgREST headers.

    With `user_token`, the request runs as that user and the RLS policies in
    006_audit_and_security.sql apply. Without one, it runs as the service role
    and bypasses RLS — correct for shared ontology tables (icd_codes, snomed_*,
    cpt_hcpcs_codes) and for the auth lookup that establishes which tenant a
    caller belongs to, and wrong for anything tenant-scoped.
    """
    key = user_token or settings.supabase_service_key or settings.supabase_anon_key
    return {
        "apikey": settings.supabase_anon_key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


async def get_client() -> httpx.AsyncClient:
    """Shared service-role client. Pooled for the process lifetime."""
    global _client, _client_loop_id
    # An httpx.AsyncClient is bound to the event loop it was created on.
    # Under pytest (one loop per TestClient request) — and under any server
    # reload — a cached client from a dead loop raises "Event loop is closed"
    # on its next use. Recreate whenever the running loop changes.
    import asyncio
    loop_id = id(asyncio.get_running_loop())
    if _client is not None and (_client.is_closed or loop_id != _client_loop_id):
        try:
            await _client.aclose()
        except Exception:
            pass
        _client = None
    if _client is None:
        _client_loop_id = loop_id
        _client = httpx.AsyncClient(
            base_url=f"{settings.supabase_url}/rest/v1",
            headers=_headers(),
            timeout=10.0,
        )
    return _client


def _effective_token(principal) -> str | None:
    """
    The token to run a tenant-scoped query under, or None to use the service
    role. Returns None unless JWT forwarding is switched on and the principal
    actually carries a token.
    """
    if not settings.db_forward_user_jwt:
        return None
    token = getattr(principal, "token", None)
    return token or None


async def request_headers(principal=None) -> dict:
    """
    Headers for a tenant-scoped request. Pass the calling Principal so RLS can
    engage when DB_FORWARD_USER_JWT is enabled; falls back to the service role
    otherwise, with the application-layer org check still enforced in routes.
    """
    return _headers(_effective_token(principal))


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


async def select_as_service(
    table: str,
    query: str = "*",
    filters: dict | None = None,
) -> list[dict]:
    """
    Explicitly service-role SELECT — bypasses RLS.

    Reserved for reads that cannot be tenant-scoped by definition: the
    `users` lookup in auth.py that establishes which tenant a caller belongs
    to, and shared ontology tables. Naming it separately keeps every RLS
    bypass in the codebase greppable.
    """
    client = await get_client()
    params = {"select": query}
    if filters:
        params.update(filters)
    response = await client.get(f"/{table}", params=params)
    response.raise_for_status()
    return response.json()


async def select_for(
    principal,
    table: str,
    query: str = "*",
    filters: dict | None = None,
    limit: int | None = None,
) -> list[dict]:
    """
    Tenant-scoped SELECT, run as the caller when JWT forwarding is enabled.

    Callers must still pass an organization_id filter derived from
    `principal.assert_org(...)` — RLS is the second line of defence here, not
    the first, because it only engages once migration 020 is applied and
    tokens have been reissued.
    """
    client = await get_client()
    params: dict = {"select": query}
    if filters:
        params.update(filters)
    if limit is not None:
        params["limit"] = str(limit)
    response = await client.get(
        f"/{table}",
        params=params,
        headers=await request_headers(principal),
    )
    response.raise_for_status()
    return response.json()


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


async def update(
    table: str,
    data: dict,
    filters: dict,
) -> list[dict]:
    """
    UPDATE rows matching PostgREST filters; returns the updated rows.

    The returned list's LENGTH is part of the contract: an optimistic-lock
    update (e.g. filters={"id": "eq.X", "status": "eq.SUBMITTED"}) that
    matched no rows returns [] — the caller must treat that as a conflict,
    not a success. Filters are REQUIRED so a bug can never update every row.
    """
    if not filters:
        raise ValueError("update() requires filters — refusing a full-table update")
    client = await get_client()
    response = await client.patch(
        f"/{table}",
        params=filters,
        content=json.dumps(data, default=str),
        headers={**_headers(), "Prefer": "return=representation"},
    )
    if response.status_code in (200, 204):
        try:
            return response.json()
        except Exception:
            return []
    detail = response.text[:300]
    log.error("update_failed", table=table, status=response.status_code, detail=detail)
    raise DatabaseError(
        f"Update of '{table}' failed ({response.status_code}): {detail}",
        table=table,
        status=response.status_code,
    )


async def delete(table: str, filters: dict) -> list[dict]:
    """
    DELETE rows matching PostgREST filters; returns the deleted rows.

    Filters are REQUIRED — a missing filter in PostgREST deletes the whole
    table, so an accidental empty dict must fail loudly rather than quietly
    emptying production data.
    """
    if not filters:
        raise ValueError("delete() requires filters — refusing a full-table delete")
    client = await get_client()
    response = await client.delete(
        f"/{table}",
        params=filters,
        headers={**_headers(), "Prefer": "return=representation"},
    )
    if response.status_code in (200, 204):
        try:
            return response.json()
        except Exception:
            return []
    detail = response.text[:300]
    log.error("delete_failed", table=table, status=response.status_code, detail=detail)
    raise DatabaseError(
        f"Delete from '{table}' failed ({response.status_code}): {detail}",
        table=table,
        status=response.status_code,
    )


async def upsert_icd_code_from_who(
    code: str, description: str, icd_version: str
) -> None:
    """
    Cache a WHO API result into the icd_codes table.

    Uses PostgREST upsert (on_conflict=code) so existing hand-curated rows
    are NEVER overwritten. Only inserts if the code is truly new.
    Fires silently — all errors are swallowed so a cache miss never blocks
    the main request pipeline.

    Called with asyncio.create_task() from who_icd_service after a successful
    WHO API search so there is zero latency impact on the user.
    """
    if not code or not description:
        return
    try:
        client = await get_client()
        # Must match icd_codes columns (003_medical_ontology.sql): version + system,
        # not icd_version / source (PostgREST PGRST204 if unknown columns).
        ver = (icd_version or "ICD-11").strip()
        ver_u = ver.upper()
        if "11" in ver_u:
            system_uri = "http://id.who.int/icd11/mms"
            version_col = ver if ver else "ICD-11"
        else:
            system_uri = "http://hl7.org/fhir/sid/icd-10"
            version_col = ver if ver else "ICD-10"

        payload = {
            "code":               code.strip(),
            "description":        description.strip(),
            "chapter":            "WHO API cache",
            "category":           "supplemental",
            "is_billable":        True,
            "is_cc":              False,
            "is_mcc":             False,
            "version":            version_col,
            "system":             system_uri,
            "base_reimbursement": 5000.0,  # Conservative default until manually set
        }
        response = await client.post(
            "/icd_codes",
            content=json.dumps(payload, default=str),
            headers={
                **_headers(),
                "Prefer": "resolution=ignore-duplicates,return=minimal",
                # resolution=ignore-duplicates: silently skip if code already exists
                # return=minimal: no response body needed for a background task
            },
            params={"on_conflict": "code"},
        )
        if response.status_code in (200, 201, 204):
            log.info("who_icd_cache_upsert_ok", code=code, version=icd_version)
        else:
            log.warning(
                "who_icd_cache_upsert_skipped",
                code=code,
                status=response.status_code,
                detail=response.text[:200],
            )
    except Exception as exc:
        # Never let a background cache write break the main pipeline
        log.warning("who_icd_cache_upsert_error", code=code, error=str(exc))
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
