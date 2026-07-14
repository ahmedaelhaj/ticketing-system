"""
Shared pytest fixtures for the whole backend test suite.

Uses a real SQLite file (not :memory:) as the test database, so it behaves
the same way across requests as it does in the ad hoc verification scripts
used throughout development. The app's own startup event (create_all + seed)
runs automatically when TestClient makes its first request, so tests don't
need to duplicate that setup.
"""
import os
import tempfile
import uuid

import pytest

# These MUST be set before anything under `app.*` is imported, since
# app.core.config.Settings reads them at import time.
_TEST_DB_FD, _TEST_DB_PATH = tempfile.mkstemp(suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH}"
os.environ["UPLOAD_ROOT"] = tempfile.mkdtemp()
os.environ["JWT_SECRET"] = "test-secret-not-for-production"
os.environ["FIRST_SUPER_ADMIN_EMAIL"] = "admin@company.com"
os.environ["FIRST_SUPER_ADMIN_PASSWORD"] = "ChangeMe123!"

from fastapi.testclient import TestClient  # noqa: E402
import app.main as app_main  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app_main.app) as c:
        yield c


@pytest.fixture(scope="session")
def login(client):
    """Returns a helper: login(email, password='12345') -> auth headers dict."""
    def _login(email: str, password: str = "12345") -> dict:
        r = client.post("/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200, f"login failed for {email}: {r.text}"
        return {"Authorization": f'Bearer {r.json()["access_token"]}'}
    return _login


@pytest.fixture(scope="session")
def super_admin_headers(login):
    return login("admin@company.com", "ChangeMe123!")


@pytest.fixture(scope="session")
def hr_admin_headers(login):
    return login("hr@gmail.com")


@pytest.fixture(scope="session")
def finance_admin_headers(login):
    return login("finance@gmail.com")


@pytest.fixture(scope="session")
def it_admin_headers(login):
    return login("it@gmail.com")


@pytest.fixture(scope="session")
def hr_user_headers(login):
    return login("oelhaj@gmail.com")


@pytest.fixture(scope="session")
def hr_user2_headers(login):
    return login("belhaj@gmail.com")


@pytest.fixture(scope="session")
def it_user_headers(login):
    return login("aelhaj@gmail.com")


@pytest.fixture(scope="session")
def team_ids(client, super_admin_headers):
    """{'HR': ..., 'Finance': ..., 'IT': ..., 'Administration': ...} team id lookup."""
    r = client.get("/teams", headers=super_admin_headers)
    assert r.status_code == 200
    return {t["name"]: t["id"] for t in r.json()}


def unique(prefix: str) -> str:
    """Short unique suffix for test data that must not collide with the demo
    seed or with other tests (team names, emails)."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"
