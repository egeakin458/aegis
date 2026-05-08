# STATUS

Live project state. Update this when work moves; archive entries to git history when superseded. CLAUDE.md should not carry anything that belongs here.

---

## Current Focus — Pre-Deployment Hardening (2026-05-08)

Backend live on Railway. Frontend deployed on Vercel (`https://frontend-tau-bice-65.vercel.app`). 286/286 tests pass.

Working through the priority list before thesis demo. API key auth fully active: frontend sends `Authorization: Bearer ${NEXT_PUBLIC_API_KEY}` on all calls (REST, SSE, ZIP download); Railway `API_KEY` set and enforced (401 on unauthenticated requests confirmed).

**What shipped (2026-05-08):**
- Railway persistent storage: Volume at `/data`, `init_db()` creates parent dir, `railway.toml` added, persistence verified across redeploy
- API key auth activated: `Authorization` header wired into `client.ts`/`sse.ts`/`output-viewer`; ZIP download converted to fetch+blob; `API_KEY` set on Railway after Vercel deploy
- Frontend deployed to Vercel; TypeScript type mismatch (`CustomerConfig` → `CustomerConfigV2`) fixed

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
3. **~~Build sandbox leaks `ANTHROPIC_API_KEY`~~** — **DONE** (`app/pipeline/build_checker.py`). `_run_full_build` now passes an explicit env allowlist to `next build`. `**os.environ` is no longer spread.
4. **~~SQLite on ephemeral Railway filesystem~~** — **DONE** (`backend/app/db/database.py`, `railway.toml`). Railway Volume mounted at `/data`; `DATABASE_PATH=/data/aegis.db` and `OUTPUT_DIR=/data/outputs` set. `init_db()` creates parent directory before connecting.
5. **`_sanitize_path` prefix-collision bug** (`output_storage.py:23`) — `startswith` check is bypassable if `output_dir` is a prefix of another path. Fix: use `Path.resolve().is_relative_to(base)`.

### Priority List (ranked impact × urgency)

| # | Item | File(s) | Status |
|---|------|---------|--------|
| 0 | **Activate API key auth** — `Authorization: Bearer` header wired in frontend (REST + SSE + ZIP download); `API_KEY` set on Railway | `client.ts`, `sse.ts`, `output-viewer/index.tsx`, Railway env vars | ✓ |
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
- **Developer agent timeout**: Complex domains (e.g. ecommerce) can hit the Anthropic 20-min request limit. Use simpler domains for live demo; item #6 (pipeline timeout) will surface this cleanly once done.

### Env Var Checklist for Railway + Vercel

**Backend (Railway):**
- `ANTHROPIC_API_KEY` ✓ set
- `DATABASE_PATH` ✓ set → `/data/aegis.db`
- `OUTPUT_DIR` ✓ set → `/data/outputs`
- `BUILD_SANDBOX_DIR` → verify relative-to-cwd on Railway
- `API_KEY` ✓ set and enforced
- `ALLOWED_ORIGINS` → set once frontend is deployed on Vercel

**Frontend (Vercel — deployed at `https://frontend-tau-bice-65.vercel.app`):**
- `NEXT_PUBLIC_API_URL` ✓ set → `https://aegis-production-bbbd.up.railway.app`
- `NEXT_PUBLIC_API_KEY` ✓ set

---

## Pending Next Steps (carried forward)

1. Tighten Developer system prompt: `PATCH /api/tasks/:id` + concrete route examples
2. Run a clean benchmark on a simple domain (e.g. todo) — ecommerce run on 2026-05-08 failed due to Anthropic 20-min request timeout on Developer agent; item #6 (pipeline timeout) will prevent silent hangs

**Running a generated app locally:**
Generated apps live in `backend/outputs/<run_id>/`. `npm install` fails on Node v24 because `better-sqlite3` requires native compilation incompatible with v24. Switch to Node 18 or 20 via nvm (`nvm use 18`), then `npm install && npm run dev` works as a standard Next.js app on `http://localhost:3000`. The sandbox stubs `better-sqlite3` only for build-check purposes — customer apps need the real package.

**Known deviation (not a bug):**
- Developer generated `PUT /api/tasks/:id/complete` instead of `PATCH /api/tasks/:id`. Functionally correct; the benchmark's keyword evaluator still passes. Worth noting for a future Developer prompt tightening pass.

---

## Recently Shipped (for short-term context — prune after a few weeks)

- **Railway persistent storage** (2026-05-08) — Volume mounted at `/data`; `init_db()` creates parent dir before `aiosqlite.connect`; `backend/railway.toml` added with start command + health check; persistence verified: run state survives a full redeploy.
- **Pipeline Refactor v0.2.0** (merged 2026-05-03, tag `v0.2.0-pipeline-refactor`) — 6-phase refactor: state-machine handler registry, API timeout + retry, `feature_id` threading, typed schema batch, `BUILD_CHECK` state, `CodePatch` patch-based revisions.
- **DDC v1** (merged 2026-05-03) — replaces conversational `CustomerConfig` with the 4D contract (Actor / DomainEntity / UseCase / BusinessRule + Relationships) enforcing referential integrity.
- **Build sandbox** (merged to `main` 2026-05-06) — pre-seeded `node_modules` + `better-sqlite3` stub + hardlink-per-run; cuts full build to ~16 s. Includes race condition fix for `PIPELINE_COMPLETE` / `save_output` ordering. `enable_full_build_check` now defaults `True`.
