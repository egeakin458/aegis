"""
Tests for API key authentication on /api/pipeline routes.

Auth contract:
- If settings.api_key == "", auth is disabled (every request passes).
- If settings.api_key is set, requests must send `Authorization: Bearer <key>`.
- Wrong key or missing header → 401.
- The /health endpoint is always public.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(autouse=True)
def mock_db():
    """Mirror the autouse fixture from test_api.py so app startup doesn't hit DB."""
    with (
        patch("app.main.init_db", new_callable=AsyncMock),
        patch("app.main.close_db", new_callable=AsyncMock),
        patch("app.main.settings"),
    ):
        yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestAuthDisabled:
    """When api_key is empty string, auth must be a no-op."""

    def test_no_header_passes_when_key_empty(self, client):
        with (
            patch("app.api.auth.settings") as mock_settings,
            patch("app.api.routes.runner_manager") as mock_manager,
            patch("app.api.routes.repo") as mock_repo,
        ):
            mock_settings.api_key = ""
            mock_manager.get_entry.return_value = None
            mock_repo.get_run = AsyncMock(return_value=None)

            response = client.get("/api/pipeline/run-x/status")

            # 404 (run not found) — not 401 — proves auth was bypassed.
            assert response.status_code == 404


class TestAuthEnabled:
    """When api_key is set, the Bearer token must match."""

    def test_missing_header_returns_401(self, client):
        with patch("app.api.auth.settings") as mock_settings:
            mock_settings.api_key = "secret-key-123"

            response = client.get("/api/pipeline/run-x/status")

            assert response.status_code == 401
            assert response.json()["detail"] == "Missing or invalid Authorization header"

    def test_wrong_scheme_returns_401(self, client):
        with patch("app.api.auth.settings") as mock_settings:
            mock_settings.api_key = "secret-key-123"

            response = client.get(
                "/api/pipeline/run-x/status",
                headers={"Authorization": "Basic secret-key-123"},
            )

            assert response.status_code == 401

    def test_wrong_key_returns_401(self, client):
        with patch("app.api.auth.settings") as mock_settings:
            mock_settings.api_key = "secret-key-123"

            response = client.get(
                "/api/pipeline/run-x/status",
                headers={"Authorization": "Bearer wrong-key"},
            )

            assert response.status_code == 401
            assert response.json()["detail"] == "Invalid API key"

    def test_correct_key_passes(self, client):
        with (
            patch("app.api.auth.settings") as mock_settings,
            patch("app.api.routes.runner_manager") as mock_manager,
            patch("app.api.routes.repo") as mock_repo,
        ):
            mock_settings.api_key = "secret-key-123"
            mock_manager.get_entry.return_value = None
            mock_repo.get_run = AsyncMock(return_value=None)

            response = client.get(
                "/api/pipeline/run-x/status",
                headers={"Authorization": "Bearer secret-key-123"},
            )

            # 404 (run not found) — proves auth passed and the route ran.
            assert response.status_code == 404


class TestHealthAlwaysPublic:
    """The /health endpoint must remain reachable without auth, even when key is set."""

    def test_health_no_auth_when_key_set(self, client):
        with patch("app.api.auth.settings") as mock_settings:
            mock_settings.api_key = "secret-key-123"

            response = client.get("/health")

            assert response.status_code == 200
            assert response.json()["status"] == "ok"
