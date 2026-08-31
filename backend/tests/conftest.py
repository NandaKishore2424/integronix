"""
tests/conftest.py — shared pytest configuration for Integronix backend tests.

Provides:
  - pytest markers registration (avoids PytestUnknownMarkWarning)
  - sys.path fixup (backend root added so imports resolve)
  - Optional .env loading for integration tests
"""

import os
import sys
import pytest

# Ensure backend root (parent of tests/) is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: mark test as requiring a live backend + Supabase connection"
    )


@pytest.fixture(scope="session", autouse=True)
def load_dotenv_once():
    """Load .env file once per test session so integration tests get credentials."""
    try:
        from dotenv import load_dotenv
        env_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"
        )
        if os.path.exists(env_path):
            load_dotenv(env_path)
    except ImportError:
        pass


# ── Authentication override ───────────────────────────────────────────────────
# Every /api/v1 endpoint now resolves an authenticated Principal. Tests get a
# deterministic one via FastAPI's dependency_overrides rather than minting real
# JWTs, so the suite exercises route logic without needing a live auth session.
#
# TEST_ORG_ID must match the organization seeded by
# migrations/seeds/002_demo_tenant_and_users.sql for the integration tests to
# see any rows — tenant scoping is now enforced on every query.

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
    """Unauthenticated TestClient — for asserting endpoints reject anonymous callers."""
    from fastapi.testclient import TestClient
    import main
    return TestClient(main.app)
