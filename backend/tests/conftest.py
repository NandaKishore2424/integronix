"""
tests/conftest.py — shared pytest configuration for Integronix backend tests.

Two tiers of test live in this suite:

  unit        — no network. Runs anywhere, including CI with no secrets.
                This is the default `pytest` run and what CI gates on.
  integration — hits live Supabase and live Groq. Marked @pytest.mark.integration
                and skipped automatically when credentials are absent.

`config.Settings` requires supabase_url / supabase_anon_key / groq_api_key and
raises at import time when they are missing, which would make every app module
unimportable in CI. So before any app module loads we backfill placeholder
values for whatever is still missing. Placeholders are only ever used to let
modules import — any test that would actually reach the network is an
integration test, and those are skipped unless real credentials are present.
"""

import os
import sys

import pytest

# Backend root on sys.path so `import config`, `import main` resolve.
BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_ROOT)


# ── Environment bootstrap (must run before any app import) ───────────────────

def _load_dotenv_if_present() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    env_path = os.path.join(BACKEND_ROOT, ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)


_REQUIRED_SETTINGS = ("SUPABASE_URL", "SUPABASE_ANON_KEY", "GROQ_API_KEY")
_PLACEHOLDERS = {
    "SUPABASE_URL": "http://localhost:1/placeholder",
    "SUPABASE_ANON_KEY": "placeholder-anon-key",
    "GROQ_API_KEY": "placeholder-groq-key",
}


def _has_live_credentials() -> bool:
    """True when every required setting holds a real value, not a placeholder."""
    return all(
        os.environ.get(k) and os.environ[k] != _PLACEHOLDERS[k]
        for k in _REQUIRED_SETTINGS
    )


_load_dotenv_if_present()
LIVE_CREDENTIALS = _has_live_credentials()

for _key in _REQUIRED_SETTINGS:
    os.environ.setdefault(_key, _PLACEHOLDERS[_key])


# ── Markers and skip policy ──────────────────────────────────────────────────

def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: requires a live backend, Supabase and Groq connection",
    )


def pytest_collection_modifyitems(config, items):
    """Skip integration tests when there are no real credentials to use."""
    if LIVE_CREDENTIALS:
        return
    skip = pytest.mark.skip(reason="no live credentials — integration tests skipped")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


# ── Authentication fixtures ──────────────────────────────────────────────────
# Every /api/v1 endpoint resolves an authenticated Principal. Tests get a
# deterministic one via FastAPI's dependency_overrides rather than minting real
# JWTs, so route logic is exercised without a live auth session.
#
# TEST_ORG_ID must match an organization that actually has seeded rows, or the
# integration tests will see nothing — tenant scoping is enforced on every query.

TEST_ORG_ID = os.getenv("TEST_ORG_ID", "00000000-0000-0000-0000-000000000001")
TEST_PAYER_ORG_ID = os.getenv("TEST_PAYER_ORG_ID", TEST_ORG_ID)


@pytest.fixture
def hospital_principal():
    from auth import Principal
    return Principal(
        auth_id="test-auth-hospital",
        user_id="test-user-hospital",
        email="coder@test.local",
        organization_id=TEST_ORG_ID,
        role="admin",
        org_type="hospital",
        token="test-token",
    )


@pytest.fixture
def payer_principal():
    from auth import Principal
    return Principal(
        auth_id="test-auth-payer",
        user_id="test-user-payer",
        email="adjudicator@test.local",
        organization_id=TEST_PAYER_ORG_ID,
        role="admin",
        org_type="insurance_payer",
        token="test-token",
    )


@pytest.fixture
def client(hospital_principal):
    """TestClient authenticated as a hospital admin."""
    from fastapi.testclient import TestClient
    from auth import get_principal
    import main

    main.app.dependency_overrides[get_principal] = lambda: hospital_principal
    try:
        yield TestClient(main.app)
    finally:
        main.app.dependency_overrides.clear()


@pytest.fixture
def payer_client(payer_principal):
    """TestClient authenticated as a payer admin."""
    from fastapi.testclient import TestClient
    from auth import get_principal
    import main

    main.app.dependency_overrides[get_principal] = lambda: payer_principal
    try:
        yield TestClient(main.app)
    finally:
        main.app.dependency_overrides.clear()


@pytest.fixture
def anon_client():
    """Unauthenticated TestClient — asserts endpoints reject anonymous callers."""
    from fastapi.testclient import TestClient
    import main
    return TestClient(main.app)


# ── Database seam ────────────────────────────────────────────────────────────

class FakeDB:
    """
    Stand-in for the async data layer, for route tests that must not touch a
    database.

    Every data access in the app now goes through database.py — select,
    select_one, insert, update, rpc — so this one seam covers all of it.
    Routes bind these names at import time (`from database import select`),
    so patching must target the ROUTE module's namespace, not database's.

    Queue a return value per call with `on(...)`; anything unqueued returns
    the type-appropriate empty value. Every call is recorded in `.calls` so a
    test can assert what the route asked the database to do — which is how the
    optimistic-lock filters are verified without a live Postgres.
    """

    def __init__(self):
        self.calls: list[tuple] = []
        self._queues: dict[str, list] = {}

    def on(self, op: str, *values):
        self._queues.setdefault(op, []).extend(values)
        return self

    def _take(self, op, default):
        q = self._queues.get(op)
        if q:
            value = q.pop(0)
            if isinstance(value, Exception):
                raise value
            return value
        return default

    async def select(self, table, query="*", filters=None, limit=None):
        self.calls.append(("select", table, filters))
        return self._take("select", [])

    async def select_one(self, table, query="*", filters=None):
        self.calls.append(("select_one", table, filters))
        return self._take("select_one", None)

    async def insert(self, table, data):
        self.calls.append(("insert", table, data))
        return self._take("insert", {"id": "00000000-0000-0000-0000-0000000000ff"})

    async def update(self, table, data, filters):
        self.calls.append(("update", table, filters))
        return self._take("update", [{"id": "00000000-0000-0000-0000-0000000000ff"}])

    async def rpc(self, fn, params):
        self.calls.append(("rpc", fn, params))
        return self._take("rpc", {"ok": True})

    def filters_for(self, op, table):
        """Filters passed to the first matching call — used to assert locks."""
        for kind, name, payload in self.calls:
            if kind == op and name == table:
                return payload
        return None


DB_FUNCTIONS = ("select", "select_one", "insert", "update", "rpc")

_VENV_MARKER = os.path.join("backend", "venv")


def _is_first_party(module) -> bool:
    """True for our own modules — not stdlib, not installed packages."""
    path = getattr(module, "__file__", None)
    return bool(path) and path.startswith(BACKEND_ROOT) and _VENV_MARKER not in path


@pytest.fixture
def fake_db():
    """
    Substitute the async data layer everywhere it is reachable.

    `from database import select_one` binds a NEW name in the importing
    module, so patching `database.select_one` alone leaves every from-import
    still pointing at the original function. Patching only the route module
    has the mirror problem: a helper the route calls (get_org_settings, say)
    holds its own binding and goes straight to the network — which passes
    locally against real Supabase and fails in CI.

    So: patch the database module, then walk every already-imported
    first-party module and rebind any attribute that IS one of the original
    functions. Self-maintaining — a new consumer is covered the moment it is
    imported.

    The originals are captured and restored HERE rather than through
    monkeypatch. The set of patch targets is computed at run time, and a
    target missed by teardown leaves a stale fake bound in another module —
    which then fails the identity check on the next test, so that module is
    silently skipped and its calls escape to the real network. That produced
    a health-check test which passed alone and failed in the suite. Explicit
    save/restore of exactly what was patched removes the ambiguity.
    """
    import sys
    import database
    # Import the whole app BEFORE capturing originals. The walk can only patch
    # modules that already exist, and a module first imported DURING a patched
    # test binds `from database import select` to the fake that happens to be
    # active at that moment — then outlives the fixture, because it was not in
    # the patch list to restore. routes.health was imported this way (via
    # main) inside a claims test and stayed bound to a dead fake for the rest
    # of the session, which made its health test pass alone and fail in the
    # suite. Importing main here forces every route module to exist first.
    import main  # noqa: F401

    db = FakeDB()
    originals = {name: getattr(database, name) for name in DB_FUNCTIONS}
    patched: list[tuple[object, str, object]] = []

    def _patch(target, name, replacement):
        patched.append((target, name, getattr(target, name)))
        setattr(target, name, replacement)

    for name in DB_FUNCTIONS:
        _patch(database, name, getattr(db, name))

    # Only first-party modules. Probing attributes on arbitrary third-party
    # modules is both wasteful and side-effecting — some (scipy) raise
    # deprecation warnings from a module-level __getattr__ merely on access.
    for module in list(sys.modules.values()):
        if module is None or module is database or not _is_first_party(module):
            continue
        for name, original in originals.items():
            if getattr(module, name, None) is original:
                _patch(module, name, getattr(db, name))

    try:
        yield db
    finally:
        for target, name, original in reversed(patched):
            setattr(target, name, original)
