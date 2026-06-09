"""
tests/conftest.py
─────────────────────────────────────────────────────────────────────────────
Shared pytest fixtures available to all tests.
"""

import pytest

from app import create_app


@pytest.fixture(scope="session")
def app():
    """Create an application instance configured for testing."""
    _app = create_app("testing")
    _app.config.update({"TESTING": True})
    return _app


@pytest.fixture()
def client(app):
    """Flask test client — resets between each test function."""
    return app.test_client()


@pytest.fixture()
def runner(app):
    """Flask CLI test runner."""
    return app.test_cli_runner()