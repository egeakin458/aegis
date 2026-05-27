# Plan: Scrub subprocess env in `_run_full_build`

**Written against:** `main` @ 9c37f7b
**Goal:** Replace `**os.environ` with a minimal allowlist when invoking `next build` so Developer-generated JS cannot read `ANTHROPIC_API_KEY` or other server secrets.

---

## Background (read this before starting)

### What exists today

- File: `backend/app/pipeline/build_checker.py`
- Function: `_run_full_build(code_output, run_id)` at line **214**
- The bug is at lines **257–264**:

  ```python
  # Subprocess env: production, no telemetry, contained HOME
  env = {
      **os.environ,
      "NODE_ENV": "production",
      "CI": "1",
      "NEXT_TELEMETRY_DISABLED": "1",
      "HOME": str(workdir),
  }
  ```

- This `env` dict is passed to `asyncio.create_subprocess_exec("npx", "next", "build", ..., env=env, ...)` at line **266**. The Developer agent's JS (e.g., `app/page.js`, `app/api/*/route.js`) executes inside `next build` and inherits the full env via `process.env`. Anything in `os.environ` of the FastAPI server process — `ANTHROPIC_API_KEY`, `API_KEY`, `DATABASE_PATH`, cloud creds — becomes readable from generated code and exfiltratable via a `fetch()` call during build.

### What the fix must do

Replace the `**os.environ` spread with an explicit minimal env dict containing only what `next build` (Next.js 14 App Router, `npx`, no native deps in sandbox) actually needs:

- `PATH` — required to find `node`, `npx`, system tools
- `HOME` — overridden to `str(workdir)` for npm cache scoping
- `NODE_ENV=production`
- `CI=1`
- `NEXT_TELEMETRY_DISABLED=1`

Optional pass-throughs (only if already set in `os.environ`):

- `TMPDIR`, `TEMP`, `TMP` — temp-file roots (platform-dependent)
- `NODE_PATH` — module resolution overrides on some setups
- `npm_config_cache` — npm cache override

Anything else (notably `ANTHROPIC_API_KEY`, `API_KEY`, `DATABASE_PATH`, `DATABASE_URL`) must NOT be present.

### Compatibility notes

- `_run_full_build` is called only by `run_build_check` at line **125** of the same file. No external callers, no schema changes, fully backward-compatible.
- The build sandbox itself does not require any custom env vars — it's a fixed pre-installed Next.js project.
- `os` is already imported at the top of `build_checker.py`.

### Test gotchas

- `test_build_checker.py` already has a working pattern for this exact code path — see `TestFullBuildPath.test_full_build_attempted_when_enabled` (lines 204–230). Reuse the fake-sandbox + `patch("asyncio.create_subprocess_exec", ...)` pattern.
- The existing test uses `AsyncMock(side_effect=_fake_exec)` where `_fake_exec(*args, **kwargs)` returns the mock proc. To capture the `env` kwarg, the `side_effect` callable can record `kwargs["env"]` into an outer-scope list.
- No DB / FastAPI fixtures required for `build_checker.py`.

---

### Task 1: Failing test (TDD red step)

**Files:**
- Modify: `backend/tests/test_build_checker.py`

- [ ] **Step 1: Add a new test method to `TestFullBuildPath` that captures the subprocess env and asserts the allowlist.**

  Append the following method inside the existing `class TestFullBuildPath:` block in `backend/tests/test_build_checker.py` (after `test_sandbox_missing_fails_loud`, before the next class):

  ```python
      @pytest.mark.asyncio
      async def test_full_build_subprocess_env_is_scrubbed(self, tmp_path, monkeypatch):
          """Secrets in os.environ must NOT leak into the `next build` subprocess env."""
          # Inject a fake secret into the parent process env.
          monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret-leaked")
          monkeypatch.setenv("API_KEY", "server-api-key-leaked")
          monkeypatch.setenv("DATABASE_PATH", "/tmp/should-not-leak.db")

          # Minimal fake sandbox so _run_full_build proceeds past the sandbox check.
          fake_sandbox = tmp_path / "sandbox"
          (fake_sandbox / "node_modules").mkdir(parents=True)
          (fake_sandbox / "package.json").write_text("{}")
          (fake_sandbox / "next.config.js").write_text("module.exports = {};")
          monkeypatch.setattr("app.config.settings.build_sandbox_dir", str(fake_sandbox))
          monkeypatch.setattr("app.config.settings.enable_full_build_check", True)

          captured_envs: list[dict] = []

          mock_proc = MagicMock()
          mock_proc.returncode = 0
          mock_proc.communicate = AsyncMock(return_value=(b"Build OK\n", b""))

          async def _fake_exec(*args, **kwargs):
              captured_envs.append(kwargs.get("env"))
              return mock_proc

          with (
              patch("app.pipeline.build_checker._check_js_syntax", new=AsyncMock(return_value=[])),
              patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=_fake_exec)),
          ):
              result = await run_build_check(
                  _make_code_output(_minimal_valid_files()),
                  run_id="test-run-scrub",
              )

          assert result.full_build_attempted is True
          # The full-build subprocess is the one whose env contains NODE_ENV=production.
          build_envs = [e for e in captured_envs if e and e.get("NODE_ENV") == "production"]
          assert len(build_envs) == 1, f"Expected one full-build subprocess, got envs: {captured_envs}"
          env = build_envs[0]

          # Secrets MUST be absent.
          assert "ANTHROPIC_API_KEY" not in env, "ANTHROPIC_API_KEY leaked into next build subprocess"
          assert "API_KEY" not in env, "API_KEY leaked into next build subprocess"
          assert "DATABASE_PATH" not in env, "DATABASE_PATH leaked into next build subprocess"

          # Required keys MUST be present.
          assert "PATH" in env, "PATH must be passed through so npx/node are findable"
          assert env.get("NODE_ENV") == "production"
          assert env.get("CI") == "1"
          assert env.get("NEXT_TELEMETRY_DISABLED") == "1"
          assert env.get("HOME", "").endswith("test-run-scrub")
  ```

- [ ] **Step 2: Run the new test and verify it fails.**

  ```bash
  cd /home/ege/projects/aegis/backend && pytest tests/test_build_checker.py::TestFullBuildPath::test_full_build_subprocess_env_is_scrubbed -xvs
  ```

  Expected failure (current code spreads `**os.environ`, so the assertion `"ANTHROPIC_API_KEY" not in env` fails):

  ```
  AssertionError: ANTHROPIC_API_KEY leaked into next build subprocess
  assert 'ANTHROPIC_API_KEY' not in {... 'ANTHROPIC_API_KEY': 'sk-secret-leaked', ...}
  ```

- [ ] **Step 3: Commit the failing test.**

  ```bash
  cd /home/ege/projects/aegis && git add backend/tests/test_build_checker.py && git commit -m "test(build_checker): assert next build subprocess env is scrubbed of secrets"
  ```

---

### Task 2: Implementation — minimal env allowlist

**Files:**
- Modify: `backend/app/pipeline/build_checker.py`

- [ ] **Step 1: Replace the env construction block at lines 257–264.**

  Locate this block in `backend/app/pipeline/build_checker.py` (showing 5 lines of context above and below for clarity):

  ```python
          # Write generated source files
          for code_file in code_output.files:
              dest = workdir / code_file.path
              dest.parent.mkdir(parents=True, exist_ok=True)
              dest.write_text(code_file.content, encoding="utf-8")

          # Subprocess env: production, no telemetry, contained HOME
          env = {
              **os.environ,
              "NODE_ENV": "production",
              "CI": "1",
              "NEXT_TELEMETRY_DISABLED": "1",
              "HOME": str(workdir),
          }
          try:
              proc = await asyncio.create_subprocess_exec(
                  "npx", "next", "build",
                  cwd=str(workdir),
                  env=env,
  ```

  Replace it with:

  ```python
          # Write generated source files
          for code_file in code_output.files:
              dest = workdir / code_file.path
              dest.parent.mkdir(parents=True, exist_ok=True)
              dest.write_text(code_file.content, encoding="utf-8")

          # Subprocess env: explicit allowlist only.
          # NEVER spread os.environ here — the Developer agent's JS runs inside
          # `next build` and any var present would be readable via process.env,
          # creating an exfiltration path for ANTHROPIC_API_KEY and other secrets.
          env: dict[str, str] = {
              "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
              "HOME": str(workdir),
              "NODE_ENV": "production",
              "CI": "1",
              "NEXT_TELEMETRY_DISABLED": "1",
          }
          for optional_key in ("TMPDIR", "TEMP", "TMP", "NODE_PATH", "npm_config_cache"):
              value = os.environ.get(optional_key)
              if value is not None:
                  env[optional_key] = value
          try:
              proc = await asyncio.create_subprocess_exec(
                  "npx", "next", "build",
                  cwd=str(workdir),
                  env=env,
  ```

- [ ] **Step 2: Run the failing test and verify it now passes.**

  ```bash
  cd /home/ege/projects/aegis/backend && pytest tests/test_build_checker.py::TestFullBuildPath::test_full_build_subprocess_env_is_scrubbed -xvs
  ```

  Expected output:

  ```
  tests/test_build_checker.py::TestFullBuildPath::test_full_build_subprocess_env_is_scrubbed PASSED
  ============================== 1 passed in ...s ==============================
  ```

- [ ] **Step 3: Commit the implementation.**

  ```bash
  cd /home/ege/projects/aegis && git add backend/app/pipeline/build_checker.py && git commit -m "fix(build_checker): scrub subprocess env to minimal allowlist

Replace **os.environ spread with explicit allowlist (PATH, HOME, NODE_ENV,
CI, NEXT_TELEMETRY_DISABLED, plus optional TMPDIR/TEMP/TMP/NODE_PATH/
npm_config_cache pass-through) when invoking next build. Prevents
Developer-generated JS from reading ANTHROPIC_API_KEY or other server
secrets via process.env during the sandbox build."
  ```

---

### Task 3: Regression — full test suite

- [ ] **Step 1: Run the build_checker test file in full.**

  ```bash
  cd /home/ege/projects/aegis/backend && pytest tests/test_build_checker.py -xvs
  ```

  Expected: every test passes, including the three pre-existing `TestFullBuildPath` tests (`test_full_build_not_attempted_when_disabled`, `test_full_build_attempted_when_enabled`, `test_sandbox_missing_fails_loud`) plus the new `test_full_build_subprocess_env_is_scrubbed`.

  ```
  ============================== N passed in ...s ==============================
  ```

- [ ] **Step 2: Run the entire backend test suite.**

  ```bash
  cd /home/ege/projects/aegis/backend && pytest tests/
  ```

  Expected: all tests pass, no regressions. If anything fails, read the failure carefully — this change only touches the `next build` subprocess env, so unrelated failures indicate either a pre-existing flake or that another test is asserting on `os.environ` pass-through (unlikely; address by reading the failure message and adjusting the test, not by widening the allowlist).

---

### Task 4: STATUS.md — mark item #3 complete

**Files:**
- Modify: `STATUS.md`

- [ ] **Step 1: Update the Hard Blockers narrative entry (line 29).**

  Replace this exact line:

  ```
  3. **Build sandbox leaks `ANTHROPIC_API_KEY`** — `_run_full_build` passes `**os.environ` to the `next build` subprocess (`build_checker.py:259`). Developer-generated JS runs with the API key in scope. A DDC prompt injection can exfiltrate it. Scrub env to a minimal allowlist.
  ```

  With:

  ```
  3. **~~Build sandbox leaks `ANTHROPIC_API_KEY`~~** — **DONE** (`app/pipeline/build_checker.py`). `_run_full_build` now passes an explicit env allowlist (PATH, HOME, NODE_ENV, CI, NEXT_TELEMETRY_DISABLED, plus optional TMPDIR/TEMP/TMP/NODE_PATH/npm_config_cache) to `next build`. `**os.environ` is no longer spread, so Developer-generated JS cannot read server secrets via `process.env`.
  ```

- [ ] **Step 2: Update the priority table row (line 39).**

  Replace this exact line:

  ```
  | 3 | Scrub subprocess env in `_run_full_build` | `build_checker.py` | ☐ |
  ```

  With:

  ```
  | 3 | Scrub subprocess env in `_run_full_build` | `build_checker.py` | ✓ |
  ```

- [ ] **Step 3: Commit the STATUS update.**

  ```bash
  cd /home/ege/projects/aegis && git add STATUS.md && git commit -m "chore(status): mark subprocess env scrub complete"
  ```
