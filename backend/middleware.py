"""
middleware.py — cross-cutting HTTP concerns.

RequestContextMiddleware gives every request a correlation id, an access log
line, and a Server-Timing header. Without it, "my submission failed at 3pm"
is unanswerable: the logs hold thousands of interleaved lines from concurrent
requests with nothing tying one request's lines together.

The id is echoed back as X-Request-ID, and error responses already quote a
reference, so a user can hand over a string that leads straight to their
request in the logs.
"""

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from logger import get_logger, request_id_var

log = get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"

# Paths that must not produce an access-log line on every call. A load
# balancer polls /health every few seconds; logging each one buries the
# traffic that matters.
_QUIET_PATHS = {"/health", "/health/live"}


def _client_request_id(request: Request) -> str | None:
    """
    Honour an inbound X-Request-ID so a trace spans the proxy and the app —
    but only if it is short and printable. It reaches the logs, and an
    attacker-controlled value must not be able to inject newlines or bloat
    every log line.
    """
    candidate = request.headers.get(REQUEST_ID_HEADER)
    if not candidate:
        return None
    candidate = candidate.strip()
    if 0 < len(candidate) <= 64 and candidate.isprintable() and " " not in candidate:
        return candidate
    return None


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = _client_request_id(request) or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = time.perf_counter()

        quiet = request.url.path in _QUIET_PATHS

        try:
            response = await call_next(request)
        except Exception as exc:
            # An unhandled exception would otherwise produce a bare 500 with
            # no correlation id, leaving the client nothing to quote.
            duration_ms = int((time.perf_counter() - started) * 1000)
            log.error(
                "request_failed",
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
                error=type(exc).__name__,
                exc_info=True,
            )
            request_id_var.reset(token)
            return JSONResponse(
                status_code=500,
                content={"detail": f"Internal server error. Reference: {request_id}"},
                headers={REQUEST_ID_HEADER: request_id},
            )

        duration_ms = int((time.perf_counter() - started) * 1000)
        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers["Server-Timing"] = f"app;dur={duration_ms}"

        if not quiet:
            log.info(
                "request_completed",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                duration_ms=duration_ms,
            )

        request_id_var.reset(token)
        return response
