# STATUS

Live project state. Update this when work moves; archive entries to git history when superseded. CLAUDE.md should not carry anything that belongs here.

---

## Current Focus — Pre-Deployment Hardening (2026-05-07)

`feat/build-sandbox` merged to `main`. Full build check enabled by default. 270/270 tests pass.

Deployment readiness audit completed (2026-05-07). Findings logged below. Next phase is working through the priority list before Railway + Vercel deployment and thesis demo.

**What shipped (2026-05-06):**
- Build sandbox merged: pre-seeded `node_modules` + `better-sqlite3` stub + hardlink-per-run; full `next build` in ~16 s
- Race condition fixed: `PIPELINE_COMPLETE` now emits after `save_output()` writes `manifest.json` — no more 404 on `GET /output`
- `enable_full_build_check: bool = True` flipped on `main` (commit `07bb3b2`)
- Benchmark: 5/5 features, 5/5 unit tests, 100%

---

## Deployment Readiness Audit (2026-05-07)

Full codebase audit performed. Findings ranked by impact × urgency.

### Hard Blockers — fix before any public deployment

1. **~~CORS broken~~** — **DONE** (`app/main.py`). `allow_origin_regex` now covers all `*.vercel.app` subdomains; `ALLOWED_ORIGIN` env var allows a custom production domain.
2. **~~No API auth on `POST /start`~~** — **DONE** (`app/api/auth.py`). Bearer token enforced on all `/api/pipeline` routes; disabled when `API_KEY=""` (dev mode).
3. **~~Build sandbox leaks `ANTHROPIC_API_KEY`~~** — **DONE** (`app/pipeline/build_checker.py`). `_run_full_build` now passes an explicit env allowlist (PATH, HOME, NODE_ENV, CI, NEXT_TELEMETRY_DISABLED, plus optional TMPDIR/TEMP/TMP/NODE_PATH/npm_config_cache) to `next build`. `**os.environ` is no longer spread, so Developer-generated JS cannot read server secrets via `process.env`.
4. **SQLite on ephemeral Railway filesystem** — `aegis.db` and `backend/outputs/` disappear on every redeploy. Need a Railway Volume mount; set `DATABASE_PATH` and `OUTPUT_DIR` to the volume path.
5. **`_sanitize_path` prefix-collision bug** (`output_storage.py:23`) — `startswith` check is bypassable if `output_dir` is a prefix of another path (e.g., `/data/out` passes for `/data/output_attacker/...`). Fix: use `Path.resolve().is_relative_to(base)`.

### Priority List (ranked impact × urgency)

| # | Item | File(s) | Status |
|---|------|---------|--------|
| 1 | Add API key auth on `POST /start` and SSE endpoints | `routes.py`, `config.py` | ✓ |
| 2 | Fix CORS regex | `main.py` | ✓ |
| 3 | Scrub subprocess env in `_run_full_build` | `build_checker.py` | ✓ |
| 4 | Wire `BUILD_CHECK` result into QA Reviewer context | `runner.py`, `qa_reviewer.py` | ✓ |
| 5 | Persistent storage on Railway (Volume mount for SQLite + outputs) | `config.py`, deploy config | ✓ |
| 6 | Top-level pipeline timeout (`asyncio.wait_for`) | `runner.py` | ☐ |
| 7 | Tighten Developer prompt: PATCH routing + concrete code examples | `developer.py` | ☐ |
| 8 | Post-validate QA verdict consistency (no "approve" with critical issues) | `runner.py`, `agent_outputs.py` | ☐ |
| 9 | Startup sweep — mark in-flight DB runs as FAILED on restart | `manager.py` or `main.py` lifespan | ☐ |
| 10 | Fix `_sanitize_path` with `Path.is_relative_to()` | `output_storage.py` | ☐ |

### Other Weaknesses (lower urgency, worth tracking)

- Validation retries only once; no fallback model on second failure (`base.py`)
- No top-level pipeline timeout — can theoretically hang 30+ min
- LLM raw response not logged on validation failure — can't post-mortem bad outputs
- QA scoring unanchored — LLM can score 4/5 with critical issues listed; no consistency check
- `feature_id` threading is prompt-convention-only, not schema-validated
- No "cancel run" button for users
- DB persistence is fire-and-forget (`asyncio.create_task`) — DB can diverge from what user saw in SSE
- Context window risk on revisions: DDC + design + previous code may exceed limits on complex projects
- Anthropic client instantiated per agent, never closed — fd leak on long-running server (`base.py`)
- SSE queue bounded at 1000; `put_nowait` silently drops events on overflow (`manager.py`)
- No structured log correlation between SSE events and DB events (no run_id in framework logs)

### Thesis Demo Risks & Mitigations

- **Live API failure / rate limit**: Pre-run at least one full pipeline and keep the outputs + DB. Have a `?run={id}` replay URL ready as fallback.
- **Build sandbox state**: Run `setup_build_sandbox.sh` fresh on demo machine. Know the `ENABLE_FULL_BUILD_CHECK=false` escape hatch.
- **Network blip during SSE**: Verify `?run={id}` refresh-safe replay works end-to-end before the panel.
- **Clarification loop surprise**: Use Quick intake mode with a domain you've benchmarked (e.g., the todo fixture).
- **Long wall-clock time (~3–5 min)**: Brief the panel in advance; have a pre-recorded run to cut to if needed.

### Env Var Checklist for Railway + Vercel

**Backend (Railway):**
- `ANTHROPIC_API_KEY` (required)
- `DATABASE_PATH` → Railway Volume path (e.g., `/data/aegis.db`)
- `OUTPUT_DIR` → Railway Volume path (e.g., `/data/outputs`)
- `BUILD_SANDBOX_DIR` → verify relative-to-cwd on Railway
- `API_KEY` → once auth is implemented
- `ALLOWED_ORIGINS` → prod frontend URL

**Frontend (Vercel):**
- `NEXT_PUBLIC_API_URL` → Railway backend URL

---

## Pending Next Steps (carried forward)

1. Tighten Developer system prompt: `PATCH /api/tasks/:id` + concrete route examples
2. Wire `BUILD_CHECK` result into QA Reviewer's input context
3. Run a second benchmark (e-commerce domain) to confirm generalisation before thesis demo

**Running a generated app locally:**
Generated apps live in `backend/outputs/<run_id>/`. `npm install` fails on Node v24 because `better-sqlite3` requires native compilation incompatible with v24. Switch to Node 18 or 20 via nvm (`nvm use 18`), then `npm install && npm run dev` works as a standard Next.js app on `http://localhost:3000`. The sandbox stubs `better-sqlite3` only for build-check purposes — customer apps need the real package.

**Known deviation (not a bug):**
- Developer generated `PUT /api/tasks/:id/complete` instead of `PATCH /api/tasks/:id`. Functionally correct; the benchmark's keyword evaluator still passes. Worth noting for a future Developer prompt tightening pass.

---

## Recently Shipped (for short-term context — prune after a few weeks)

- **Pipeline Refactor v0.2.0** (merged 2026-05-03, tag `v0.2.0-pipeline-refactor`) — 6-phase refactor: state-machine handler registry, API timeout + retry, `feature_id` threading, typed schema batch, `BUILD_CHECK` state, `CodePatch` patch-based revisions.
- **DDC v1** (merged 2026-05-03) — replaces conversational `CustomerConfig` with the 4D contract (Actor / DomainEntity / UseCase / BusinessRule + Relationships) enforcing referential integrity.
- **Build sandbox** (merged to `main` 2026-05-06) — pre-seeded `node_modules` + `better-sqlite3` stub + hardlink-per-run; cuts full build to ~16 s. Includes race condition fix for `PIPELINE_COMPLETE` / `save_output` ordering. `enable_full_build_check` now defaults `True`.
