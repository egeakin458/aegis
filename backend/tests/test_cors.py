"""
CORS preflight tests.

Verifies that:
- localhost:3000 (dev frontend) is allowed
- arbitrary *.vercel.app subdomains are NOT allowed (no wildcard regex)
- unknown origins are rejected (no Access-Control-Allow-Origin header)
- an explicit production domain set via ALLOWED_ORIGIN is allowed

Uses httpx.AsyncClient through the ASGI transport so the full middleware
stack (including CORSMiddleware) actually runs.
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.main import app


@pytest.fixture(autouse=True)
def mock_db():
    """Mock startup hooks and disable auth — mirrors test_api.py."""
    with (
        patch("app.main.init_db", new_callable=AsyncMock),
        patch("app.main.close_db", new_callable=AsyncMock),
        patch("app.main.settings"),
        patch("app.api.auth.settings") as mock_auth_settings,
    ):
        mock_auth_settings.api_key = ""
        yield


async def _preflight(origin: str) -> httpx.Response:
    """Issue a CORS preflight OPTIONS request against /health."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.options(
            "/health",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "content-type",
            },
        )


@pytest.mark.asyncio
async def test_localhost_origin_allowed():
    """http://localhost:3000 (Next.js dev) must pass CORS preflight."""
    resp = await _preflight("http://localhost:3000")
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"


@pytest.mark.asyncio
async def test_vercel_preview_origin_rejected():
    """Arbitrary *.vercel.app subdomains must NOT pass — wildcard regex was removed."""
    origin = "https://aegis-pr-42.vercel.app"
    resp = await _preflight(origin)
    assert "access-control-allow-origin" not in {k.lower() for k in resp.headers.keys()}


@pytest.mark.asyncio
async def test_vercel_production_origin_rejected_without_env():
    """Bare *.vercel.app must NOT pass without ALLOWED_ORIGIN set."""
    origin = "https://aegis.vercel.app"
    resp = await _preflight(origin)
    assert "access-control-allow-origin" not in {k.lower() for k in resp.headers.keys()}


@pytest.mark.asyncio
async def test_unknown_origin_rejected():
    """An unrelated origin must NOT receive an Access-Control-Allow-Origin header."""
    resp = await _preflight("https://evil.com")
    assert "access-control-allow-origin" not in {k.lower() for k in resp.headers.keys()}


@pytest.mark.asyncio
async def test_explicit_allowed_origin_env_var(monkeypatch):
    """When ALLOWED_ORIGIN is set, that domain must pass.

    We rebuild the app so the new settings value is picked up by the
    middleware constructor.
    """
    monkeypatch.setenv("ALLOWED_ORIGIN", "https://aegis.example.com")

    # Reload settings + app so the new env var feeds the regex.
    import importlib

    from app import config as config_module
    importlib.reload(config_module)
    from app import main as main_module
    importlib.reload(main_module)

    transport = httpx.ASGITransport(app=main_module.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.options(
            "/health",
            headers={
                "Origin": "https://aegis.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert resp.headers.get("access-control-allow-origin") == "https://aegis.example.com"
