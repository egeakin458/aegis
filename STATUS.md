# STATUS

Live project state. Update this when work moves; archive entries to git history when superseded. CLAUDE.md should not carry anything that belongs here.

---

## Current Focus — Merge feat/build-sandbox → main (2026-05-06)

Smoke test passed. `feat/build-sandbox` is ready to merge.

**Smoke test results (run_id: f97ec5c2, 2026-05-06):**
1. `BUILD_CHECK_START` → `BUILD_CHECK_COMPLETE` — sandbox path fired, 17 files checked in ~16 s ✓
2. Full build duration: ~16 s (under 60 s target) ✓
3. Generated app: `next build` compiles clean (19 files, all routes) ✓
4. Endpoints present: `POST/GET /api/tasks`, `DELETE /api/tasks/:id`, `PUT /api/tasks/:id/complete`, `GET/POST /api/categories` ✓
5. QA Reviewer: first-pass approve, no revision cycle ✓
6. Benchmark score: **5/5 features, 5/5 unit tests, 100%** ✓

**Bug fixed during smoke test:**
- `PIPELINE_COMPLETE` was emitted before `save_output()` wrote `manifest.json` → clients got 404 on `GET /output`. Fixed by moving terminal event emission to `_finalize_run()` after `save_output()` completes (`manager.py`). Regression test added in `TestFinalizeRunOrdering`.

**Next steps** *(written by claude-sonnet-4-6)*:
1. Merge `feat/build-sandbox` → `main` — branch is green (270/270 tests, smoke test 100%)
2. On `main`, flip `enable_full_build_check: bool = True` in `backend/app/config.py` as a separate atomic commit
3. Tighten Developer system prompt to generate `PATCH /api/tasks/:id` (inline state update) rather than a separate `PUT /:id/complete` route — keeps generated APIs predictable and matching DDC use case intent
4. Consider wiring `BUILD_CHECK` result into QA Reviewer's input context so QA can reference actual build evidence rather than inferring it
5. Run a second benchmark (different domain, e.g. e-commerce) to confirm the pipeline generalises beyond the todo fixture before thesis demo

**Running a generated app locally:**
Generated apps live in `backend/outputs/<run_id>/`. `npm install` fails on Node v24 because `better-sqlite3` requires native compilation incompatible with v24. Switch to Node 18 or 20 via nvm (`nvm use 18`), then `npm install && npm run dev` works as a standard Next.js app on `http://localhost:3000`. The sandbox stubs `better-sqlite3` only for build-check purposes — customer apps need the real package.

**Known deviation (not a bug):**
- Developer generated `PUT /api/tasks/:id/complete` instead of `PATCH /api/tasks/:id`. Functionally correct; the benchmark's keyword evaluator still passes. Worth noting for a future Developer prompt tightening pass.

---

## Recently Shipped (for short-term context — prune after a few weeks)

- **Pipeline Refactor v0.2.0** (merged 2026-05-03, tag `v0.2.0-pipeline-refactor`) — 6-phase refactor: state-machine handler registry, API timeout + retry, `feature_id` threading, typed schema batch, `BUILD_CHECK` state, `CodePatch` patch-based revisions.
- **DDC v1** (merged 2026-05-03) — replaces conversational `CustomerConfig` with the 4D contract (Actor / DomainEntity / UseCase / BusinessRule + Relationships) enforcing referential integrity.
- **Build sandbox** (on `feat/build-sandbox`, smoke test passed 2026-05-06) — pre-seeded `node_modules` + `better-sqlite3` stub + hardlink-per-run; cuts full build to ~16 s. Includes race condition fix for `PIPELINE_COMPLETE` / `save_output` ordering.
