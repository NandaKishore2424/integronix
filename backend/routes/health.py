"""
routes/health.py — liveness and readiness.

The distinction matters to whatever is supervising the process:

  /health/live   Is this process running and able to answer? Never touches a
                 dependency. A failing liveness check means RESTART ME.
  /health        Is this instance ready to serve traffic? Checks the database.
                 A failing readiness check means STOP SENDING ME REQUESTS —
                 restarting would not help, because the fault is downstream.

Conflating the two is how a database blip turns into an endless restart loop.

This endpoint previously always returned 200, reporting {"database": "error"}
in the BODY when the check failed. Load balancers and container health checks
read the status code, not the body, so a completely broken instance was kept
in rotation. It also ran two count() queries over 98K ICD codes and 379K
SNOMED concepts and then discarded both results — on every poll.
"""

import time

from fastapi import APIRouter, Response, status

from config import settings
from database import select
from logger import get_logger

router = APIRouter(tags=["Health"])
log = get_logger(__name__)

# A readiness probe must fail fast. Hanging until the default client timeout
# makes the supervisor's own timeout the effective deadline, which is worse
# than reporting "not ready" promptly.
_DB_CHECK_TIMEOUT_S = 3.0


@router.get("/health/live", summary="Liveness — is the process up?")
async def liveness():
    """No dependencies touched. If this cannot answer, the process is wedged."""
    return {"status": "alive"}


@router.get("/health", summary="Readiness — can this instance serve traffic?")
async def readiness(response: Response):
    import asyncio

    started = time.perf_counter()
    database_ok = False
    detail = None

    try:
        # One cheap indexed read. Enough to prove the connection, the
        # credentials and PostgREST are all working, without scanning a table.
        await asyncio.wait_for(
            select("icd_codes", query="code", filters={"limit": "1"}),
            timeout=_DB_CHECK_TIMEOUT_S,
        )
        database_ok = True
    except asyncio.TimeoutError:
        detail = f"database did not respond within {_DB_CHECK_TIMEOUT_S}s"
    except Exception as exc:
        # The exception text can carry connection strings; log it, and keep
        # the public body to a category.
        log.error("health_database_check_failed", error=str(exc))
        detail = "database unreachable"

    body = {
        "status": "ready" if database_ok else "not_ready",
        "database": "connected" if database_ok else "error",
        "version": app_version(),
        "env": settings.app_env,
        "checks": {"database": {"ok": database_ok}},
        "duration_ms": int((time.perf_counter() - started) * 1000),
    }
    if detail:
        body["checks"]["database"]["detail"] = detail

    if not database_ok:
        # The part that matters: an unready instance must SAY so in the status
        # code, or nothing upstream can act on it.
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return body


def app_version() -> str:
    """Image/build identifier, injected at container build time."""
    import os

    return os.getenv("APP_VERSION", "dev")
