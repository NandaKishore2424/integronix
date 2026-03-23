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
