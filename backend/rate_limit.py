"""
rate_limit.py — per-caller token bucket for expensive endpoints.

/code/run spends money on every call: a Groq completion plus several database
round trips. Authentication stopped anonymous abuse, but one logged-in user
can still loop the endpoint and exhaust the account's whole free-tier quota
for everybody else.

WHY IN-PROCESS AND NOT REDIS
The service runs as a single instance, so an in-process bucket is exact.
Adding Redis would buy correctness only once there are several instances, and
would introduce a network dependency, another failure mode, and another thing
to operate — for a limiter that would still be approximate under partition.
The moment a second instance exists this becomes per-instance rather than
global, and the state moves to Redis. That is the trigger to watch for, and
the reason is recorded here rather than left implicit.

WHY A TOKEN BUCKET
A fixed window ("60 per minute") lets a caller fire 60 requests at 11:59:59
and 60 more at 12:00:00 — 120 in one second, at the boundary. A token bucket
refills continuously, so the long-run rate is capped while a short burst is
still allowed, which is what a human clicking a button actually needs.
"""

import asyncio
import time
from dataclasses import dataclass, field

from fastapi import Depends, HTTPException, Request, status

from auth import Principal, get_principal
from config import settings
from logger import get_logger

log = get_logger(__name__)


@dataclass
class _Bucket:
    tokens: float
    updated_at: float


@dataclass
class TokenBucketLimiter:
    """
    `rate` tokens per second, up to `capacity` in reserve.

    One asyncio.Lock guards the whole table. The critical section is a few
    arithmetic operations with no await inside it, so contention is
    negligible and the read-modify-write can never interleave between
    concurrent requests from the same caller.
    """

    capacity: float
    rate: float
    _buckets: dict[str, _Bucket] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def take(self, key: str, now: float | None = None) -> tuple[bool, float]:
        """Consume one token. Returns (allowed, retry_after_seconds)."""
        now = time.monotonic() if now is None else now
        async with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                # A new caller starts with a full bucket minus this request.
                self._buckets[key] = _Bucket(tokens=self.capacity - 1, updated_at=now)
                return True, 0.0

            elapsed = max(0.0, now - bucket.updated_at)
            bucket.tokens = min(self.capacity, bucket.tokens + elapsed * self.rate)
            bucket.updated_at = now

            if bucket.tokens >= 1:
                bucket.tokens -= 1
                return True, 0.0

            # Time until one whole token exists again.
            retry_after = (1 - bucket.tokens) / self.rate if self.rate > 0 else 60.0
            return False, retry_after

    def reset(self) -> None:
        """Drop all state — used by tests."""
        self._buckets.clear()


# The pipeline limiter. Defaults are deliberately generous for a human
# operator (a coder runs a handful of notes a minute) and tight enough that a
# script cannot drain the Groq quota.
pipeline_limiter = TokenBucketLimiter(
    capacity=float(settings.rate_limit_pipeline_burst),
    rate=float(settings.rate_limit_pipeline_per_minute) / 60.0,
)


async def enforce_pipeline_rate_limit(
    request: Request,
    principal: Principal = Depends(get_principal),
) -> Principal:
    """
    FastAPI dependency for the pipeline endpoints.

    Keyed on the authenticated user, not the IP: several coders behind one
    hospital NAT share an address, and throttling them as one caller would
    punish colleagues for each other's usage.
    """
    if not settings.rate_limit_enabled:
        return principal

    allowed, retry_after = await pipeline_limiter.take(principal.user_id)
    if not allowed:
        log.warning(
            "rate_limited",
            auth_id=principal.auth_id,
            path=request.url.path,
            retry_after_s=round(retry_after, 1),
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many pipeline runs. Please wait a moment and try again.",
            headers={"Retry-After": str(max(1, int(retry_after) + 1))},
        )
    return principal
