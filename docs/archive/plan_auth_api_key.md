# Plan: API Key Authentication for Aegis Backend

**Written against:** `main` @ `ac6ecc6`
**Goal:** Protect all `/api/pipeline` routes with a Bearer token so random internet users can't burn Anthropic credits.

---

## Background (read this before starting)

**Repo root:** `/home/ege/projects/aegis`. All paths below are relative to repo root.

**What exists today:**

1. `backend/app/config.py` (line 31) already declares `api_key: str = ""` on the `Settings` class. Reuse it — do not add a new setting. The settings singleton is `from app.config import settings`.

2. `backend/app/api/routes.py` defines a single `APIRouter` at module scope (`router = APIRouter()`, line 31) with these routes:
   - `POST /start` (line 43)
   - `GET /{run_id}/events` (line 63) — SSE stream via `EventSourceResponse`
   - `POST /{run_id}/clarification` (line 132)
   - `GET /{run_id}/status` (line 145)
   - `GET /{run_id}/output` (line 184)
   - `GET /{run_id}/output/download` (line 222)

3. `backend/app/main.py` mounts the router at prefix `/api/pipeline` (line 50) and exposes a public `GET /health` (line 53). CORS is at lines 39-48 with `allow_headers=["Content-Type", "Authorization"]` — already includes `Authorization`; no CORS change needed.

4. `backend/tests/test_api.py` uses `fastapi.testclient.TestClient(app)` and an autouse `mock_db` fixture (lines 24-32) that patches `app.main.settings`. Note: it patches `app.main.settings`, not `app.api.routes.settings` — when writing auth tests you patch `app.api.auth.settings`.

5. **SSE auth decision — header-only, no `?token=` query param.** The frontend uses `@microsoft/fetch-event-source` (not native `EventSource`), which supports custom headers. Query-string tokens leak into server logs, browser history, and Referer headers. No query-param fallback is needed or implemented.

6. **Backward compatibility:** existing tests send no `Authorization` header. With `api_key=""` (the default), auth is disabled, so those tests pass without changes. New auth tests in Task 4 set the key explicitly.

7. **Frontend follow-on (out of scope here):** threading `API_KEY` into `frontend/lib/api/sse.ts` and other fetch calls is a separate plan.

---

### Task 1: Write failing tests for the auth dependency (TDD red step)

**Files:**
- Create: `backend/tests/test_auth.py`

- [ ] **Step 1: Create the test file.**

```python
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
```

- [ ] **Step 2: Run the new tests and confirm they fail (red).**

```bash
cd /home/ege/projects/aegis/backend && pytest tests/test_auth.py -v
```

Expected: `TestAuthEnabled` tests fail (routes return 404 instead of 401 — auth doesn't exist yet). `TestAuthDisabled` and `TestHealthAlwaysPublic` should pass. This is the expected red state.

- [ ] **Step 3: Commit the failing tests.**

```bash
cd /home/ege/projects/aegis && git add backend/tests/test_auth.py
git commit -m "test(auth): add failing tests for API key bearer auth"
```

---

### Task 2: Implement the auth dependency

**Files:**
- Create: `backend/app/api/auth.py`

- [ ] **Step 1: Create the auth dependency module.**

```python
"""
API key authentication dependency for /api/pipeline routes.

Contract:
- If settings.api_key == "", authentication is disabled (dev mode).
- Otherwise, requests must include `Authorization: Bearer <api_key>`.

SSE note: this is a header-only dependency. The frontend uses
@microsoft/fetch-event-source (not native EventSource), which supports custom
headers, so a `?token=` query-string fallback is intentionally NOT provided —
query-string tokens leak into logs, browser history, and Referer headers.
"""

from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.config import settings


async def require_api_key(authorization: str | None = Header(default=None)) -> None:
    """
    FastAPI dependency that enforces a Bearer token matching settings.api_key.

    Returns None on success; raises HTTPException(401) on failure.
    Disabled when settings.api_key is the empty string.
    """
    expected = settings.api_key
    if not expected:
        # Auth disabled — dev mode.
        return

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )

    provided = authorization[len("Bearer "):].strip()
    if provided != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
```

- [ ] **Step 2: Commit the dependency.**

```bash
cd /home/ege/projects/aegis && git add backend/app/api/auth.py
git commit -m "feat(auth): add require_api_key bearer-token dependency"
```

---

### Task 3: Wire the dependency into the pipeline router

**Files:**
- Modify: `backend/app/api/routes.py`

The router is constructed at line 31 as `router = APIRouter()`. Attaching the dependency at the router level means all six routes inherit it automatically. `/health` in `main.py` is unaffected.

- [ ] **Step 1: Add the `Depends` import and `require_api_key` import, then attach to the router.**

In `backend/app/api/routes.py`, make two changes:

**Change 1** — update the fastapi import line (currently `from fastapi import APIRouter, Body, HTTPException`):

```python
from fastapi import APIRouter, Body, Depends, HTTPException
```

**Change 2** — add the auth import alongside the other local imports at the top of the file and update the router construction line:

```python
from app.api.auth import require_api_key
```

Then find the line:

```python
router = APIRouter()
```

And replace it with:

```python
router = APIRouter(dependencies=[Depends(require_api_key)])
```

- [ ] **Step 2: Run the auth tests and confirm all pass (green).**

```bash
cd /home/ege/projects/aegis/backend && pytest tests/test_auth.py -v
```

Expected: `6 passed`.

- [ ] **Step 3: Commit the wiring.**

```bash
cd /home/ege/projects/aegis && git add backend/app/api/routes.py
git commit -m "feat(auth): apply require_api_key dependency to pipeline router"
```

---

### Task 4: Regression — verify existing tests still pass

Existing `test_api.py` tests send no `Authorization` header. With `api_key=""` (default), auth is disabled, so they should pass without changes.

- [ ] **Step 1: Run the full backend test suite.**

```bash
cd /home/ege/projects/aegis/backend && pytest tests/ -v
```

Expected: all previously-passing tests continue to pass, plus the 6 new auth tests. Zero failures.

- [ ] **Step 2: If any test in `test_api.py` fails with a 401**, the autouse fixture isn't isolating `app.api.auth.settings`. In that case, edit `backend/tests/test_api.py` and update the `mock_db` fixture (lines 24-32) to also patch auth settings:

```python
@pytest.fixture(autouse=True)
def mock_db():
    """Mock database init/close and startup validation for all tests."""
    with (
        patch("app.main.init_db", new_callable=AsyncMock),
        patch("app.main.close_db", new_callable=AsyncMock),
        patch("app.main.settings"),
        patch("app.api.auth.settings") as mock_auth_settings,
    ):
        mock_auth_settings.api_key = ""
        yield
```

Re-run `pytest tests/ -v` and confirm green.

- [ ] **Step 3: Commit only if Step 2 was needed.**

```bash
cd /home/ege/projects/aegis && git add backend/tests/test_api.py
git commit -m "test(api): force api_key empty in autouse fixture for regression isolation"
```

If Step 2 was not needed, skip this commit.

---

### Task 5: Verify CORS already allows the Authorization header

No code change expected — this is a confirmation step.

- [ ] **Step 1: Confirm `backend/app/main.py` CORS config includes `"Authorization"` in `allow_headers`.**

The current configuration (lines 39-48) should read:

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

`"Authorization"` is present. No change needed.

- [ ] **Step 2 (optional — only if backend is running locally): smoke-test the CORS preflight.**

```bash
curl -i -X OPTIONS http://localhost:8000/api/pipeline/start \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Authorization, Content-Type"
```

Expected: response includes `access-control-allow-headers: Content-Type, Authorization`.

---

### Task 6: Document the env var and final verification

**Files:**
- Modify: `backend/.env.example` (only if it exists)

- [ ] **Step 1: Check whether `.env.example` exists.**

```bash
ls -la /home/ege/projects/aegis/backend/.env.example
```

If it does not exist, skip to Step 3.

- [ ] **Step 2: If `.env.example` exists, add the `API_KEY` entry** (do not duplicate or modify existing keys):

```
# Shared API key for frontend-backend auth. Leave empty to disable auth (local dev).
API_KEY=
```

Then commit:

```bash
cd /home/ege/projects/aegis && git add backend/.env.example
git commit -m "docs(env): document API_KEY for bearer-token auth"
```

- [ ] **Step 3: Run the full suite one final time.**

```bash
cd /home/ege/projects/aegis/backend && pytest tests/ -v
```

Expected: all green.

- [ ] **Step 4: Update STATUS.md — mark item #1 complete.**

In `docs/../STATUS.md`, in the Priority List table, change:

```
| 1 | Add API key auth on `POST /start` and SSE endpoints | `routes.py`, `config.py` | ☐ |
```

to:

```
| 1 | Add API key auth on `POST /start` and SSE endpoints | `routes.py`, `config.py` | ✓ |
```

Then commit:

```bash
cd /home/ege/projects/aegis && git add STATUS.md
git commit -m "docs(status): mark auth (#1) complete"
```

---

## What can go wrong

| Symptom | Cause | Fix |
|---------|-------|-----|
| `test_api.py` tests fail with 401 | `app.api.auth.settings` is the real settings object, not the mock | Do Task 4 Step 2 — patch `app.api.auth.settings` to `api_key=""` in autouse fixture |
| `ImportError: cannot import name 'require_api_key'` | `auth.py` not in the Python path or typo in import | Verify file is at `backend/app/api/auth.py` and import in `routes.py` is `from app.api.auth import require_api_key` |
| 422 Unprocessable Entity instead of 401 | FastAPI is rejecting the `Authorization` header before it reaches the dependency | Ensure `Header(default=None)` is used (not `Header(...)`) so the header is optional at the FastAPI layer |
| CORS error in browser after deploying | `allow_origins` glob `"https://*.vercel.app"` doesn't work (Starlette doesn't support globs) | That's a separate known bug (#2 on the priority list) — fix it in the next plan |

---

## Out of scope — follow-on plan

A separate plan is required to thread the API key through the **Next.js frontend**:
- Add `AEGIS_API_KEY` env var (server-side in Vercel).
- Update `frontend/lib/api/sse.ts` `fetchEventSource` call to pass `headers: { Authorization: \`Bearer ${key}\` }`.
- Update all other `fetch()` calls in `frontend/lib/api/` to include the header.
- Set `API_KEY` in Railway env vars and `AEGIS_API_KEY` in Vercel env vars.
