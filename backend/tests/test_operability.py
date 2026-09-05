"""
Unit tests for the operational surface: health probes, request correlation,
rate limiting and upload limits.

None of this changes a billing outcome, which is exactly why it needs tests —
it is the machinery that tells you when something else has gone wrong, and a
health check that lies is worse than none at all.
"""

import asyncio

import pytest

from logger import get_logger, request_id_var
from middleware import REQUEST_ID_HEADER, _client_request_id
from rate_limit import TokenBucketLimiter


def run(coro):
    return asyncio.run(coro)


# ── Health probes ────────────────────────────────────────────────────────────

class TestReadiness:
    """
    Regression: /health returned 200 unconditionally, putting "database":
    "error" in the BODY when the check failed. Load balancers and container
    health checks read the STATUS CODE, so a fully broken instance stayed in
    rotation and kept receiving traffic.
    """

    def test_ready_returns_200(self, anon_client, fake_db):
        fake_db.on("select", [{"code": "A00"}])
        res = anon_client.get("/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ready"
        assert res.json()["checks"]["database"]["ok"] is True

    def test_database_down_returns_503_not_200(self, anon_client, fake_db):
        fake_db.on("select", RuntimeError("connection refused"))
        res = anon_client.get("/health")
        assert res.status_code == 503, "an unready instance must say so in the status code"
        assert res.json()["status"] == "not_ready"
        assert res.json()["checks"]["database"]["ok"] is False

    def test_failure_detail_does_not_leak_internals(self, anon_client, fake_db):
        """Connection errors can carry credentials; the body gets a category."""
        fake_db.on("select", RuntimeError("could not connect to postgres://user:hunter2@db"))
        body = anon_client.get("/health").text
        assert "hunter2" not in body
        assert "postgres://" not in body

    def test_liveness_never_touches_the_database(self, anon_client, fake_db):
        """
        Liveness must not depend on anything downstream, or a database blip
        becomes an endless restart loop.
        """
        fake_db.on("select", RuntimeError("database is down"))
        res = anon_client.get("/health/live")
        assert res.status_code == 200
        assert res.json()["status"] == "alive"
        assert not fake_db.calls, "liveness must issue no queries at all"

    def test_health_is_public(self, anon_client, fake_db):
        """The probe cannot require a token — the prober does not have one."""
        fake_db.on("select", [{"code": "A00"}])
        assert anon_client.get("/health").status_code == 200
        assert anon_client.get("/health/live").status_code == 200


# ── Request correlation ──────────────────────────────────────────────────────

class TestRequestId:
    def test_every_response_carries_a_request_id(self, anon_client, fake_db):
        fake_db.on("select", [{"code": "A00"}])
        res = anon_client.get("/health")
        assert res.headers.get(REQUEST_ID_HEADER)

    def test_ids_differ_between_requests(self, anon_client, fake_db):
        fake_db.on("select", [{"code": "A00"}], [{"code": "A00"}])
        first = anon_client.get("/health").headers[REQUEST_ID_HEADER]
        second = anon_client.get("/health").headers[REQUEST_ID_HEADER]
        assert first != second

    def test_inbound_id_is_honoured_so_traces_span_the_proxy(self, anon_client, fake_db):
        fake_db.on("select", [{"code": "A00"}])
        res = anon_client.get("/health", headers={REQUEST_ID_HEADER: "trace-abc-123"})
        assert res.headers[REQUEST_ID_HEADER] == "trace-abc-123"

    @pytest.mark.parametrize("hostile", [
        "id with spaces",
        "x" * 200,                      # unbounded length on every log line
        "abc\nINFO fake log line",      # log injection
        "",
    ])
    def test_hostile_inbound_ids_are_replaced(self, hostile):
        """
        The id reaches the logs, so a client-supplied value must not be able
        to inject newlines or bloat every line. Rejected values fall back to a
        generated id rather than being sanitised in place.
        """
        assert _client_request_id(_FakeRequest({REQUEST_ID_HEADER: hostile})) is None

    def test_reasonable_inbound_id_is_accepted(self):
        assert _client_request_id(_FakeRequest({REQUEST_ID_HEADER: "abc-123"})) == "abc-123"

    def test_context_var_is_cleared_after_the_request(self, anon_client, fake_db):
        """A leaked id would mislabel the next request's log lines."""
        fake_db.on("select", [{"code": "A00"}])
        anon_client.get("/health")
        assert request_id_var.get() is None

    def test_log_lines_are_stamped_with_the_current_id(self, capsys):
        import json

        log = get_logger("test.correlation")
        token = request_id_var.set("req-xyz")
        try:
            log.info("something_happened", detail="value")
        finally:
            request_id_var.reset(token)

        line = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
        assert line["request_id"] == "req-xyz"
        assert line["detail"] == "value"


class _FakeRequest:
    def __init__(self, headers):
        self.headers = headers


# ── Rate limiting ────────────────────────────────────────────────────────────

class TestTokenBucket:
    def test_burst_is_allowed_up_to_capacity(self):
        limiter = TokenBucketLimiter(capacity=5, rate=1.0)
        results = [run(limiter.take("user-1", now=100.0))[0] for _ in range(5)]
        assert all(results)

    def test_further_requests_are_refused(self):
        limiter = TokenBucketLimiter(capacity=3, rate=1.0)
        for _ in range(3):
            run(limiter.take("user-1", now=100.0))
        allowed, retry_after = run(limiter.take("user-1", now=100.0))
        assert allowed is False
        assert retry_after > 0, "a refusal must say when to come back"

    def test_tokens_refill_over_time(self):
        limiter = TokenBucketLimiter(capacity=2, rate=1.0)  # 1 token/second
        run(limiter.take("user-1", now=100.0))
        run(limiter.take("user-1", now=100.0))
        assert run(limiter.take("user-1", now=100.0))[0] is False
        assert run(limiter.take("user-1", now=101.5))[0] is True, "1.5s buys a token"

    def test_bucket_never_refills_past_capacity(self):
        """A long idle period must not bank unlimited burst."""
        limiter = TokenBucketLimiter(capacity=3, rate=1.0)
        run(limiter.take("user-1", now=100.0))
        allowed = [run(limiter.take("user-1", now=100_000.0))[0] for _ in range(4)]
        assert allowed[:3] == [True, True, True]
        assert allowed[3] is False

    def test_callers_are_isolated_from_each_other(self):
        """One user exhausting their quota must not throttle a colleague."""
        limiter = TokenBucketLimiter(capacity=2, rate=1.0)
        run(limiter.take("noisy", now=100.0))
        run(limiter.take("noisy", now=100.0))
        assert run(limiter.take("noisy", now=100.0))[0] is False
        assert run(limiter.take("quiet", now=100.0))[0] is True

    def test_concurrent_takes_do_not_oversell_the_bucket(self):
        """
        The read-modify-write must not interleave: without the lock, N
        concurrent requests can each see the same token count and all pass.
        """
        limiter = TokenBucketLimiter(capacity=5, rate=0.0)

        async def hammer():
            return await asyncio.gather(*(limiter.take("user-1", now=100.0) for _ in range(50)))

        results = asyncio.run(hammer())
        assert sum(1 for allowed, _ in results if allowed) == 5


class TestPipelineRateLimitEndpoint:
    def test_exceeding_the_limit_returns_429_with_retry_after(self, client, fake_db, monkeypatch):
        import rate_limit

        monkeypatch.setattr(rate_limit, "pipeline_limiter",
                            TokenBucketLimiter(capacity=1, rate=0.0))

        body = {"raw_text": "x" * 50}
        fake_db.on("select_one", None, None, None, None)

        first = client.post("/api/v1/code/run", json=body)
        assert first.status_code != 429, "the first call must be allowed through"

        second = client.post("/api/v1/code/run", json=body)
        assert second.status_code == 429
        assert int(second.headers["Retry-After"]) >= 1

    def test_limiter_can_be_disabled_by_configuration(self, client, monkeypatch):
        import rate_limit
        from config import settings

        monkeypatch.setattr(settings, "rate_limit_enabled", False)
        monkeypatch.setattr(rate_limit, "pipeline_limiter",
                            TokenBucketLimiter(capacity=0, rate=0.0))

        res = client.post("/api/v1/code/run", json={"raw_text": "short"})
        assert res.status_code != 429


# ── Upload limits ────────────────────────────────────────────────────────────

class TestCappedUpload:
    """
    Regression: the handler did `await file.read()` and checked the size
    afterwards, so a 2 GB body exhausted the container before the 20 MB limit
    was ever consulted. The check ran too late to protect anything.
    """

    def test_reads_a_file_within_the_cap(self):
        from routes.code import _read_capped
        payload = b"%PDF-1.4 small file"
        assert run(_read_capped(_FakeUpload(payload), 1024)) == payload

    def test_returns_none_once_the_cap_is_passed(self):
        from routes.code import _read_capped
        assert run(_read_capped(_FakeUpload(b"x" * 5000), 1024)) is None

    def test_stops_reading_instead_of_buffering_everything(self):
        """Memory stays bounded no matter how much the client sends."""
        from routes.code import _read_capped

        upload = _FakeUpload(b"x" * (10 * 1024 * 1024))
        assert run(_read_capped(upload, 64 * 1024)) is None
        assert upload.bytes_read <= 64 * 1024 + 64 * 1024, \
            "must abort near the cap, not after consuming the whole body"

    def test_empty_upload_reads_as_empty(self):
        from routes.code import _read_capped
        assert run(_read_capped(_FakeUpload(b""), 1024)) == b""


class _FakeUpload:
    """Minimal UploadFile stand-in that serves bytes in chunks."""

    def __init__(self, data: bytes):
        self._data = data
        self._pos = 0
        self.bytes_read = 0

    async def read(self, size: int = -1) -> bytes:
        if size < 0:
            chunk = self._data[self._pos:]
        else:
            chunk = self._data[self._pos:self._pos + size]
        self._pos += len(chunk)
        self.bytes_read += len(chunk)
        return chunk
