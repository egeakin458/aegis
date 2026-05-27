# Plan: Persistent storage on Railway (Volume mount for SQLite + outputs)
**Written against:** `main` @ 1b55b7c
**Goal:** Make Aegis state survive Railway redeploys by mounting a Volume at `/data`, pointing `DATABASE_PATH` and `OUTPUT_DIR` at it, and ensuring `init_db()` creates the parent directory before opening the SQLite file.

---

## Background (read this before starting)

Railway uses an ephemeral filesystem. Today, `aegis.db` and `backend/outputs/` live next to the running process and are wiped on every redeploy. The fix has three moving parts:

1. **Railway Volume** mounted at `/data` (configured in the Railway dashboard, not in code).
2. **Environment variables** `DATABASE_PATH=/data/aegis.db` and `OUTPUT_DIR=/data/outputs` set on the Railway backend service.
3. **One code fix**: `init_db()` must create the parent directory of the SQLite path before calling `aiosqlite.connect`, otherwise the very first boot on a fresh volume fails with `sqlite3.OperationalError: unable to open database file`.

### Files involved

- `backend/app/config.py` — already defines `database_path: str = "aegis.db"` and `output_dir: str = "outputs"`, both loaded from env vars `DATABASE_PATH` / `OUTPUT_DIR` via pydantic-settings. **No change needed.**
- `backend/.env.example` — already documents the two env vars. **No change needed.**
- `backend/app/db/database.py` — current `init_db()` (lines 53–63) calls `aiosqlite.connect(path)` directly without ensuring the parent dir exists. **One-line fix.** `Path` is already imported at line 11.
- `backend/app/pipeline/output_storage.py:38` — already calls `output_dir.mkdir(parents=True, exist_ok=True)`. **No change needed.**
- `backend/tests/test_database.py` — uses an autouse `setup_db` fixture that calls `init_db(":memory:")` and `close_db()`. Our new test must opt out of memory-only behavior; the cleanest way is a standalone `@pytest.mark.asyncio` test that, after the autouse fixture has run, re-initializes against a `tmp_path` location and then closes again. The autouse teardown will then run on an already-closed connection — `close_db()` is idempotent (no-op when `_connection is None`), so this is safe.
- `backend/railway.toml` — does not exist; create it.
- `STATUS.md` — Priority List item #5 to mark complete.

### Compatibility notes

- `init_db()` accepts `:memory:` and absolute paths. `Path(":memory:").parent` returns `Path(".")`, and `Path(".").mkdir(parents=True, exist_ok=True)` is a safe no-op, so adding the `mkdir` call before `aiosqlite.connect` does not regress in-memory test usage.
- `close_db()` already handles being called when `_connection is None`. No risk of double-close errors.
- The Railway Volume mount is a dashboard-only operation; `railway.toml` does not currently support declaring volumes.

---

### Task 1: Failing test — `init_db` creates parent directory (TDD red)

**Files:**
- Modify: `backend/tests/test_database.py`

- [ ] **Step 1: Append the failing test to `backend/tests/test_database.py`.**

  Add this function at the end of the file (after the existing tests, outside any class). It uses `tmp_path` to point at a directory that does not yet exist on disk, exercising the codepath that fails today.

  ```python
  @pytest.mark.asyncio
  async def test_init_db_creates_parent_directory(tmp_path):
      """init_db must create the parent directory if it does not exist.

      This is the Railway Volume case: on a fresh volume mount at /data,
      the directory exists but on first boot we may target a nested path
      that does not. The function must create it rather than crash with
      sqlite3.OperationalError.
      """
      path = str(tmp_path / "subdir" / "aegis.db")
      assert not Path(path).parent.exists()
      try:
          await init_db(path)
          assert Path(path).exists()
      finally:
          await close_db()
  ```

  Verify the imports at the top of `backend/tests/test_database.py` already include `pytest`, `Path` (from `pathlib`), `init_db`, and `close_db`. If `Path` is not imported, add `from pathlib import Path` near the other imports.

- [ ] **Step 2: Run the test to confirm it fails (red).**

  ```bash
  cd /home/ege/projects/aegis/backend && venv/bin/pytest tests/test_database.py::test_init_db_creates_parent_directory -xvs
  ```

  Expected output contains:
  ```
  sqlite3.OperationalError: unable to open database file
  ```
  Test status: `FAILED`.

- [ ] **Step 3: Commit the failing test.**

  ```bash
  git add backend/tests/test_database.py && git commit -m "test(db): assert init_db creates parent directory"
  ```

---

### Task 2: Implementation — `init_db` creates parent directory (TDD green)

**Files:**
- Modify: `backend/app/db/database.py`

- [ ] **Step 1: Update `init_db()` to create the parent directory before connecting.**

  Replace the current `init_db()` function (lines 53–63) with this complete updated version. The only change is the new `Path(path).parent.mkdir(...)` line; everything else is preserved verbatim.

  ```python
  async def init_db(db_path: str | None = None) -> None:
      """Initialize the database: open connection and create tables."""
      global _connection
      if _connection is not None:
          await _connection.close()
      path = db_path or settings.database_path
      logger.info("Initializing database at %s", path)
      Path(path).parent.mkdir(parents=True, exist_ok=True)
      _connection = await aiosqlite.connect(path)
      _connection.row_factory = aiosqlite.Row
      await _connection.executescript(SCHEMA_SQL)
      await _connection.commit()
  ```

  `Path` is already imported at line 11 of this file — no new imports required.

- [ ] **Step 2: Run the new test to confirm it passes (green).**

  ```bash
  cd /home/ege/projects/aegis/backend && venv/bin/pytest tests/test_database.py::test_init_db_creates_parent_directory -xvs
  ```

  Expected output: `1 passed`.

- [ ] **Step 3: Run the full database test file to confirm no regressions.**

  ```bash
  cd /home/ege/projects/aegis/backend && venv/bin/pytest tests/test_database.py -q
  ```

  Expected output: all tests pass (the previously-existing tests plus the new one).

- [ ] **Step 4: Commit the implementation.**

  ```bash
  git add backend/app/db/database.py && git commit -m "fix(db): create parent directory before opening sqlite connection"
  ```

---

### Task 3: Railway deploy config

**Files:**
- Create: `backend/railway.toml`

- [ ] **Step 1: Create `backend/railway.toml` with the deploy configuration.**

  Write the file with this exact content:

  ```toml
  [build]
  builder = "NIXPACKS"

  [deploy]
  startCommand = "uvicorn app.main:app --host 0.0.0.0 --port $PORT"
  healthcheckPath = "/health"
  healthcheckTimeout = 30
  restartPolicyType = "ON_FAILURE"
  restartPolicyMaxRetries = 3
  ```

- [ ] **Step 2: Commit the deploy config.**

  ```bash
  git add backend/railway.toml && git commit -m "chore(deploy): add railway.toml with start command and health check"
  ```

- [ ] **Step 3: Manual Railway dashboard configuration.**

  These steps cannot be automated — they happen in the Railway web UI after the commit lands and the service redeploys.

  1. Open the Railway project. Select the backend service. Go to the **Volumes** tab and click **New Volume**. Set the volume name to `aegis-data` and the mount path to `/data`. Attach it to the backend service. Save.
  2. In the same backend service, open the **Variables** tab. Add two variables:
     - `DATABASE_PATH` = `/data/aegis.db`
     - `OUTPUT_DIR` = `/data/outputs`
     Save. Railway will trigger a redeploy.
  3. After the redeploy finishes, open the service logs and confirm a line like `Initializing database at /data/aegis.db` appears with no errors. The first boot will create `/data/aegis.db` and `/data/outputs/` automatically because of the Task 2 fix and the existing `output_storage.py` `mkdir(parents=True, exist_ok=True)` call.
  4. To verify persistence: trigger a pipeline run from the frontend, wait for it to complete, then redeploy the backend service from the Railway dashboard. After the redeploy, hit `GET /api/pipeline/{run_id}/status` for the previous run — it should return the run instead of 404.

---

### Task 4: Regression — full backend test suite

- [ ] **Step 1: Run the full backend test suite.**

  ```bash
  cd /home/ege/projects/aegis/backend && venv/bin/pytest tests/ -q
  ```

  Expected: every previously-passing test still passes, plus the one new test from Task 1. No failures, no new warnings introduced by these changes.

  If any test fails, do not proceed to Task 5 — diagnose and fix before moving on.

---

### Task 5: STATUS.md update

**Files:**
- Modify: `STATUS.md`

- [ ] **Step 1: Mark Priority List item #5 as complete.**

  In `STATUS.md`, find this row in the Priority List table:

  ```
  | 5 | Persistent storage on Railway (Volume mount for SQLite + outputs) | `config.py`, deploy config | ☐ |
  ```

  Replace it with:

  ```
  | 5 | Persistent storage on Railway (Volume mount for SQLite + outputs) | `config.py`, deploy config | ✓ |
  ```

  Leave every other row untouched.

- [ ] **Step 2: Commit the status update.**

  ```bash
  git add STATUS.md && git commit -m "chore(status): mark Railway persistent storage complete"
  ```

---

## Done criteria

- `backend/app/db/database.py::init_db` creates the parent directory of the SQLite path before connecting.
- `backend/tests/test_database.py::test_init_db_creates_parent_directory` passes; full backend suite still green.
- `backend/railway.toml` exists with the start command and health check.
- Railway dashboard has a `/data` volume attached to the backend service and `DATABASE_PATH` / `OUTPUT_DIR` set to point at it.
- A pipeline run completed before a redeploy is still visible (status + outputs) after the redeploy.
- `STATUS.md` Priority List item #5 reads `✓`.
