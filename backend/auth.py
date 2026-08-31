"""
auth.py — Request authentication and the tenant boundary.

Every request that touches PHI or money resolves to a `Principal`: a verified
Supabase auth user joined to their `public.users` row (organization, role).

Two independent layers protect tenant data, deliberately:

  1. **Application layer (always on).** `Principal.organization_id` comes from
     the database, never from the request. Routes call `principal.assert_org()`
     rather than trusting a client-supplied `org_id`. This works today, with no
     database changes.

  2. **Database layer (opt-in).** When `DB_FORWARD_USER_JWT=true`, queries run
     against PostgREST with the caller's own token, so the RLS policies in
     `006_audit_and_security.sql` engage. That requires the JWT to carry
     `app_metadata.organization_id` — see migration 020. Until that migration
     is applied AND users have re-authenticated, leave the flag off: the
     policies would evaluate `organization_id = NULL` and deny everything.

Token verification prefers local signature checks (no network) and falls back
to the Supabase Auth API, which is authoritative regardless of signing
algorithm. Both paths are cached briefly to keep the hot path cheap.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Iterable, Optional

import httpx
import jwt
from fastapi import Depends, Header, HTTPException, status

from config import settings
from logger import get_logger

log = get_logger(__name__)

# Verified tokens and resolved users are cached for a short window. The TTL is
# deliberately far below Supabase's 1h access-token lifetime so a revoked or
# role-changed user loses access quickly.
_TOKEN_TTL_SECONDS = 60
_USER_TTL_SECONDS = 60

_token_cache: dict[str, tuple[float, dict]] = {}
_user_cache: dict[str, tuple[float, dict]] = {}

_MAX_CACHE_ENTRIES = 2048


def _cache_get(cache: dict, key: str, ttl: int) -> Optional[Any]:
    hit = cache.get(key)
    if not hit:
        return None
    stored_at, value = hit
    if (time.monotonic() - stored_at) > ttl:
        cache.pop(key, None)
        return None
    return value


def _cache_put(cache: dict, key: str, value: Any) -> None:
    # Crude bound — this is a per-process cache, not a general-purpose one.
    # Dropping the whole map is cheaper than tracking an LRU for this volume.
    if len(cache) >= _MAX_CACHE_ENTRIES:
        cache.clear()
    cache[key] = (time.monotonic(), value)


def reset_auth_caches() -> None:
    """Clear cached tokens/users. Used by tests and after role changes."""
    _token_cache.clear()
    _user_cache.clear()


# ── Principal ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Principal:
    """An authenticated caller, resolved against `public.users`."""

    auth_id: str                 # auth.users.id — subject of the JWT
    user_id: str                 # public.users.id
    email: str
    organization_id: str         # authoritative tenant — from the DB, not the request
    role: str                    # admin | auditor | coder | rcm | payer
    org_type: Optional[str]      # hospital | insurance_payer | ...
    token: str                   # raw access token, for RLS forwarding

    @property
    def is_payer(self) -> bool:
        return self.org_type == "insurance_payer"

    def assert_org(self, org_id: Optional[str]) -> str:
        """
        Confirm a client-supplied organization_id matches this caller's org.

        Returns the caller's own organization_id, so routes can use the return
        value directly and never thread the request-supplied value onward.
        Passing None means "use mine" and is always allowed.
        """
        if org_id and str(org_id) != str(self.organization_id):
            log.warning(
                "cross_tenant_denied",
                auth_id=self.auth_id,
                caller_org=self.organization_id,
                requested_org=org_id,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this organization's data.",
            )
        return str(self.organization_id)

    def assert_role(self, *allowed: str) -> None:
        if self.role not in allowed:
            log.warning(
                "role_denied",
                auth_id=self.auth_id,
                role=self.role,
                required=list(allowed),
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires one of: {', '.join(sorted(allowed))}.",
            )


# ── Token verification ────────────────────────────────────────────────────────

def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _verify_locally(token: str) -> Optional[dict]:
    """
    Verify an HS256 Supabase token against the project JWT secret.

    Returns None when no secret is configured, so the caller can fall back to
    the Auth API. Raises 401 when a secret IS configured and the token fails —
    a bad signature must never fall through to a second chance.
    """
    secret = (settings.supabase_jwt_secret or "").strip()
    if not secret:
        return None
    try:
        return jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="authenticated",
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Session expired. Please sign in again.")
    except jwt.InvalidTokenError as exc:
        log.warning("jwt_local_verify_failed", error=str(exc))
        raise _unauthorized("Invalid authentication token.")


async def _verify_via_auth_api(token: str) -> dict:
    """
    Ask Supabase Auth to validate the token. Authoritative and
    algorithm-agnostic (works with both legacy HS256 and asymmetric keys).
    """
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                f"{settings.supabase_url}/auth/v1/user",
                headers={
                    "apikey": settings.supabase_anon_key,
                    "Authorization": f"Bearer {token}",
                },
            )
    except httpx.HTTPError as exc:
        # Fail closed: an auth service we cannot reach is not an authorization.
        log.error("auth_api_unreachable", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is unavailable. Please retry.",
        )

    if resp.status_code != 200:
        log.warning("auth_api_rejected_token", status=resp.status_code)
        raise _unauthorized("Invalid or expired authentication token.")

    user = resp.json()
    if not user.get("id"):
        raise _unauthorized("Invalid authentication token.")

    return {
        "sub": user["id"],
        "email": user.get("email") or "",
        "app_metadata": user.get("app_metadata") or {},
    }


async def verify_token(token: str) -> dict:
    """Verify an access token and return its claims. Raises 401 if invalid."""
    cached = _cache_get(_token_cache, token, _TOKEN_TTL_SECONDS)
    if cached is not None:
        return cached

    claims = _verify_locally(token)
    if claims is None:
        claims = await _verify_via_auth_api(token)

    _cache_put(_token_cache, token, claims)
    return claims


# ── Principal resolution ──────────────────────────────────────────────────────

async def _load_user_row(auth_id: str) -> dict:
    """
    Resolve the `public.users` row for an authenticated subject.

    This read intentionally uses the service client: it is the lookup that
    establishes which tenant the caller belongs to, so it cannot itself be
    subject to a tenant filter. It is keyed strictly by the JWT subject.
    """
    cached = _cache_get(_user_cache, auth_id, _USER_TTL_SECONDS)
    if cached is not None:
        return cached

    # Imported here to avoid a circular import at module load
    # (database imports config, routes import both).
    from database import select_as_service

    rows = await select_as_service(
        "users",
        query="id, email, organization_id, role, is_active, organizations(type)",
        filters={"auth_id": f"eq.{auth_id}", "limit": "1"},
    )
    if not rows:
        log.warning("principal_no_user_row", auth_id=auth_id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No user profile is linked to this account. Contact your administrator.",
        )

    row = rows[0]
    if row.get("is_active") is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated.",
        )
    if not row.get("organization_id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is not linked to an organization.",
        )

    _cache_put(_user_cache, auth_id, row)
    return row


def _bearer(authorization: Optional[str]) -> str:
    if not authorization:
        raise _unauthorized("Missing Authorization header.")
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise _unauthorized("Authorization header must be 'Bearer <token>'.")
    return parts[1].strip()


async def get_principal(authorization: Optional[str] = Header(None)) -> Principal:
    """
    FastAPI dependency — the authenticated caller.

    Use as: `principal: Principal = Depends(get_principal)`
    """
    if not settings.auth_enabled:
        # Escape hatch for local pipeline work against a scratch database.
        # Guarded so it can never silently apply outside development.
        if settings.app_env == "production":
            raise RuntimeError(
                "AUTH_ENABLED=false is not permitted when APP_ENV=production."
            )
        log.warning("auth_disabled_dev_principal_issued")
        return Principal(
            auth_id="dev", user_id="dev", email="dev@localhost",
            organization_id=settings.dev_org_id or "00000000-0000-0000-0000-000000000000",
            role="admin", org_type="hospital", token="",
        )

    token = _bearer(authorization)
    claims = await verify_token(token)

    auth_id = claims.get("sub")
    if not auth_id:
        raise _unauthorized("Token is missing a subject claim.")

    row = await _load_user_row(str(auth_id))
    org = row.get("organizations") or {}
    if isinstance(org, list):
        org = org[0] if org else {}

    return Principal(
        auth_id=str(auth_id),
        user_id=str(row["id"]),
        email=row.get("email") or claims.get("email") or "",
        organization_id=str(row["organization_id"]),
        role=str(row.get("role") or "coder"),
        org_type=(org or {}).get("type"),
        token=token,
    )


def require_roles(*allowed: str):
    """
    Dependency factory enforcing a role allow-list.

    Use as: `principal: Principal = Depends(require_roles("admin", "rcm"))`
    """
    allowed_set: tuple[str, ...] = tuple(allowed)

    async def _dep(principal: Principal = Depends(get_principal)) -> Principal:
        principal.assert_role(*allowed_set)
        return principal

    return _dep


def require_payer_org():
    """Dependency enforcing that the caller belongs to an insurance payer org."""

    async def _dep(principal: Principal = Depends(get_principal)) -> Principal:
        if not principal.is_payer:
            log.warning(
                "payer_org_required_denied",
                auth_id=principal.auth_id,
                org_type=principal.org_type,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This endpoint is restricted to payer organizations.",
            )
        return principal

    return _dep


def roles_csv(roles: Iterable[str]) -> str:
    return ", ".join(sorted(set(roles)))
