"""
services/user_provisioning.py — create and remove Supabase Auth accounts.

Admin screens used to create accounts in the browser with
supabase.auth.signUp() — the same public endpoint that self-signup uses. That
only worked while public signup was enabled, and public signup is the one
setting that actually stops strangers creating accounts: the anon key ships in
the frontend bundle, so removing a signup page does nothing on its own. With
signup disabled, those screens broke.

Provisioning now runs on the server through the Auth admin API, which works
with public signup off and needs the service-role key — held only by the
backend.
"""
import httpx

from config import settings
from logger import get_logger

log = get_logger(__name__)

_DUPLICATE_CODES = {"email_exists", "user_already_exists"}


class ProvisioningError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class EmailAlreadyRegistered(ProvisioningError):
    """The Auth service already holds an account for this email."""


def _admin_headers() -> dict:
    key = settings.supabase_service_key
    if not key:
        raise ProvisioningError("service role key is not configured")
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=15.0)


def _error_code(response: httpx.Response) -> str | None:
    try:
        body = response.json()
    except ValueError:
        return None
    return (body.get("error_code") or body.get("code")) if isinstance(body, dict) else None


async def create_auth_user(email: str, password: str, full_name: str) -> str:
    """Create a confirmed account and return its auth.users id."""
    headers = _admin_headers()
    async with _http_client() as client:
        response = await client.post(
            f"{settings.supabase_url}/auth/v1/admin/users",
            headers=headers,
            json={
                "email": email,
                "password": password,
                # Provisioned by an admin, so there is no confirmation email to
                # wait for — the account is usable immediately.
                "email_confirm": True,
                "user_metadata": {"full_name": full_name},
            },
        )

    if response.status_code in (200, 201):
        user_id = (response.json() or {}).get("id")
        if not user_id:
            raise ProvisioningError("auth admin API returned no user id", status=response.status_code)
        return str(user_id)

    code = _error_code(response)
    if code in _DUPLICATE_CODES or (response.status_code == 422 and "already" in response.text.lower()):
        raise EmailAlreadyRegistered("an account with this email already exists", status=response.status_code)

    # Deliberately no response body in the log: it can echo the email address.
    log.error("auth_admin_create_failed", status=response.status_code, error_code=code)
    raise ProvisioningError(f"auth admin API returned {response.status_code}", status=response.status_code)


async def delete_auth_user(auth_id: str) -> None:
    """Remove an account. Already gone counts as success."""
    headers = _admin_headers()
    async with _http_client() as client:
        response = await client.delete(
            f"{settings.supabase_url}/auth/v1/admin/users/{auth_id}",
            headers=headers,
        )
    if response.status_code in (200, 204, 404):
        return
    log.error("auth_admin_delete_failed", status=response.status_code, auth_id=auth_id)
    raise ProvisioningError(f"auth admin API returned {response.status_code}", status=response.status_code)
