# Plan: Fix CORS Configuration for Vercel Deployments

**Written against:** `main` @ a8e2a42
**Goal:** Replace the broken `"https://*.vercel.app"` literal in `allow_origins` with a regex-based match so Vercel-hosted frontends can actually reach the backend.

---

## Background (read this before starting)

**Current state — the bug.** `backend/app/main.py` lines 38-48 install Starlette's `CORSMiddleware` with:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://*.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)
```

Starlette's `allow_origins` does **exact string matching**. `"https://*.vercel.app"` is a literal — no glob/regex expansion. Every Vercel preview or production URL (`https://aegis-xxx.vercel.app`) is therefore rejected. This is a hard pre-deploy blocker.

**The fix.** Starlette's `CORSMiddleware` accepts an `allow_origin_regex: str` argument that is matched (via `re.fullmatch`) against the request `Origin` header. We:

1. Drop `"https://*.vercel.app"` from `allow_origins` (keep `"http://localhost:3000"` — exact match works).
2. Add `allow_origin_regex` covering `https://<anything>.vercel.app` and (optionally) an explicit production domain pulled from a new `Settings` field `allowed_origin`.
3. Use `re.escape` on `settings.allowed_origin` before splicing it into the regex (prevents regex injection from a misconfigured env var).
4. If `allowed_origin` is empty, the regex still covers all `*.vercel.app` subdomains.

**Settings.** `backend/app/config.py` uses `pydantic-settings` with `env_file=".env"`. Adding a string field with default `""` is backward-compatible — existing `.env` files without `ALLOWED_ORIGIN` get `""` automatically. Pydantic-settings is case-insensitive on env var names by default, so `ALLOWED_ORIGIN` maps to `allowed_origin`.

**Test gotcha — TestClient does NOT exercise CORS the way you expect.** `fastapi.testclient.TestClient` (Starlette's sync test client) **does** run middleware and **does** return CORS headers, BUT for clarity and to match the existing async patterns in this codebase, the new `test_cors.py` will use `httpx.AsyncClient` with the ASGI transport plus `@pytest.mark.asyncio`. This goes through the full ASGI stack and returns real CORS headers on `OPTIONS` preflight.

A CORS preflight is an `OPTIONS` request carrying:
- `Origin: <origin>`
- `Access-Control-Request-Method: POST` (or GET)

A successful response includes `access-control-allow-origin: <origin>`. A rejected origin causes Starlette's CORS middleware to **omit** the `access-control-allow-origin` header entirely (it does not 403).

**Compatibility note — autouse `mock_db` fixture.** `backend/tests/test_api.py` lines 24-34 already patches `app.main.init_db`, `app.main.close_db`, `app.main.settings`, AND `app.api.auth.settings` with `api_key=""` (this last patch is required after the auth-key change so the auth dependency is a no-op in tests). The new `test_cors.py` MUST mirror this exact fixture or auth will reject the requests before CORS middleware runs (CORS middleware sits OUTSIDE the routing layer, so auth rejection actually still produces correct CORS headers — but mirroring the fixture also lets us assert against `/health` cleanly without 401s in non-OPTIONS tests).

**File reference (for the implementer):**
- Bug location: `backend/app/main.py:38-48`
- Settings class: `backend/app/config.py:11-50` (add field after `api_key` at line 31)
- Test fixture template: `backend/tests/test_api.py:24-40`
- Env documentation: `backend/.env.example`

---

## Task 1 — Failing tests (TDD red step)

**Files:**
- Create: `backend/tests/test_cors.py`

- [ ] **Step 1: Write the failing test file.**

Create `backend/tests/test_cors.py` with exactly this content:

```python
"""
CORS preflight tests.

Verifies that:
- localhost:3000 (dev frontend) is allowed
- arbitrary *.vercel.app subdomains (preview deployments) are allowed
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
async def test_vercel_preview_origin_allowed():
    """Any *.vercel.app subdomain must pass — this is the currently broken case."""
    origin = "https://aegis-pr-42.vercel.app"
    resp = await _preflight(origin)
    assert resp.headers.get("access-control-allow-origin") == origin


@pytest.mark.asyncio
async def test_vercel_production_origin_allowed():
    """The bare production-style Vercel URL must also pass."""
    origin = "https://aegis.vercel.app"
    resp = await _preflight(origin)
    assert resp.headers.get("access-control-allow-origin") == origin


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
```

- [ ] **Step 2: Run the new tests and confirm they fail in the expected way.**

```bash
cd /home/ege/projects/aegis/backend && pytest tests/test_cors.py -v
```

Expected:
- `test_localhost_origin_allowed` — PASS (already works today)
- `test_vercel_preview_origin_allowed` — FAIL (no `access-control-allow-origin` header — the bug)
- `test_vercel_production_origin_allowed` — FAIL (same reason)
- `test_unknown_origin_rejected` — PASS (already correct today)
- `test_explicit_allowed_origin_env_var` — FAIL (`allowed_origin` field does not exist yet)

- [ ] **Step 3: Commit the failing tests.**

```bash
cd /home/ege/projects/aegis && git add backend/tests/test_cors.py && git commit -m "test(cors): add failing preflight tests for vercel + explicit origin"
```

---

## Task 2 — Add `allowed_origin` to Settings

**Files:**
- Modify: `backend/app/config.py`

- [ ] **Step 1: Add the field.**

In `backend/app/config.py`, immediately after the existing `api_key` line (line 31), insert a new line so the API security block reads:

```python
    # API security
    api_key: str = ""  # Shared secret for frontend-backend auth
    allowed_origin: str = ""  # Optional explicit production domain for CORS (e.g. https://aegis.example.com)
```

Full diff for that block (replace the two-line block with three lines):

Before:
```python
    # API security
    api_key: str = ""  # Shared secret for frontend-backend auth
```

After:
```python
    # API security
    api_key: str = ""  # Shared secret for frontend-backend auth
    allowed_origin: str = ""  # Optional explicit production domain for CORS (e.g. https://aegis.example.com)
```

- [ ] **Step 2: Verify Settings still imports cleanly.**

```bash
cd /home/ege/projects/aegis/backend && python -c "from app.config import settings; print(repr(settings.allowed_origin))"
```

Expected: `''`

- [ ] **Step 3: Commit.**

```bash
cd /home/ege/projects/aegis && git add backend/app/config.py && git commit -m "feat(config): add allowed_origin setting for production CORS domain"
```

---

## Task 3 — Fix the CORS middleware in main.py

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: Replace the CORS block.**

In `backend/app/main.py`, replace lines 38-48 (the `# CORS — allow the Next.js frontend to connect` block through the closing `)`) with this exact content. Also add `import re` at the top of the file (with the other stdlib imports).

Full new content of `backend/app/main.py`:

```python
"""
Aegis — FastAPI application entry point.

Run with: uvicorn app.main:app --reload --port 8000
"""

import logging
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as pipeline_router
from app.config import settings
from app.db.database import close_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown hooks."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    settings.validate_required()
    await init_db()
    yield
    await close_db()


app = FastAPI(
    title="Aegis API",
    description="Multi-agent AI pipeline for software generation",
    version="0.1.0",
    lifespan=lifespan,
)


def _build_cors_origin_regex() -> str:
    """Build the allow_origin_regex pattern.

    Always matches https://<subdomain>.vercel.app. If settings.allowed_origin
    is set, also matches that exact origin (regex-escaped).
    """
    patterns = [r"https://[a-zA-Z0-9-]+\.vercel\.app"]
    if settings.allowed_origin:
        patterns.append(re.escape(settings.allowed_origin))
    return "|".join(patterns)


# CORS — allow the Next.js frontend to connect.
# localhost is matched exactly; Vercel deployments and the optional production
# domain are matched via regex (Starlette's allow_origins does NOT support globs).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_origin_regex=_build_cors_origin_regex(),
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(pipeline_router, prefix="/api/pipeline")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "aegis-backend"}
```

- [ ] **Step 2: Run the CORS tests and confirm they pass.**

```bash
cd /home/ege/projects/aegis/backend && pytest tests/test_cors.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 3: Commit.**

```bash
cd /home/ege/projects/aegis && git add backend/app/main.py && git commit -m "fix(cors): use allow_origin_regex so vercel deployments are accepted"
```

---

## Task 4 — Document the new env var in `.env.example`

**Files:**
- Modify: `backend/.env.example`

- [ ] **Step 1: Add the documentation entry.**

In `backend/.env.example`, after the `API_KEY=...` line (line 12), insert a blank line and the new entry. The "API Security" block should end up looking like:

```
# API Security - shared secret between frontend and backend
API_KEY=change-this-to-a-random-string

# Optional explicit production frontend origin for CORS.
# *.vercel.app subdomains are always allowed; set this for a custom domain.
# Leave empty if you only deploy to Vercel.
ALLOWED_ORIGIN=
```

- [ ] **Step 2: Commit.**

```bash
cd /home/ege/projects/aegis && git add backend/.env.example && git commit -m "docs(env): document ALLOWED_ORIGIN for production CORS"
```

---

## Task 5 — Regression: run the full test suite

- [ ] **Step 1: Run all backend tests.**

```bash
cd /home/ege/projects/aegis/backend && pytest tests/ -q
```

Expected: every previously-passing test still passes, plus the 5 new CORS tests. No new failures and no new warnings introduced by the CORS change.

If anything fails, diagnose before proceeding — do NOT continue to Task 6.

---

## Task 6 — Update STATUS.md

**Files:**
- Modify: `STATUS.md`

- [ ] **Step 1: Mark the CORS item complete in the Priority List.**

Find the row in the Priority List table whose item is "Fix CORS for Vercel" (item #2). Change its status cell from the in-progress / todo marker to the done marker used elsewhere in the same table (mirror the format the file already uses for completed items — do not invent a new convention).

- [ ] **Step 2: Commit.**

```bash
cd /home/ege/projects/aegis && git add STATUS.md && git commit -m "chore(status): mark CORS fix complete"
```

---

## Done criteria

- `pytest tests/test_cors.py -v` — 5/5 pass
- `pytest tests/` — all green, no new failures
- `https://aegis-xxx.vercel.app` and `https://aegis.example.com` (when `ALLOWED_ORIGIN` is set) both receive `access-control-allow-origin` on preflight; `https://evil.com` does not
- `backend/.env.example` documents `ALLOWED_ORIGIN`
- STATUS.md reflects completion
