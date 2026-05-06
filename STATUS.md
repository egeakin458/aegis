# STATUS

Live project state. Update this when work moves; archive entries to git history when superseded. CLAUDE.md should not carry anything that belongs here.

---

## Current Focus — Next improvements (2026-05-06)

`feat/build-sandbox` merged to `main`. Full build check enabled by default. 270/270 tests pass.

**What shipped (2026-05-06):**
- Build sandbox merged: pre-seeded `node_modules` + `better-sqlite3` stub + hardlink-per-run; full `next build` in ~16 s
- Race condition fixed: `PIPELINE_COMPLETE` now emits after `save_output()` writes `manifest.json` — no more 404 on `GET /output`
- `enable_full_build_check: bool = True` flipped on `main` (commit `07bb3b2`)
- Benchmark: 5/5 features, 5/5 unit tests, 100%

**Next steps:**
1. Tighten Developer system prompt to generate `PATCH /api/tasks/:id` (inline state update) rather than a separate `PUT /:id/complete` route — keeps generated APIs predictable and matching DDC use case intent
2. Consider wiring `BUILD_CHECK` result into QA Reviewer's input context so QA can reference actual build evidence rather than inferring it
3. Run a second benchmark (different domain, e.g. e-commerce) to confirm the pipeline generalises beyond the todo fixture before thesis demo

**Running a generated app locally:**
Generated apps live in `backend/outputs/<run_id>/`. `npm install` fails on Node v24 because `better-sqlite3` requires native compilation incompatible with v24. Switch to Node 18 or 20 via nvm (`nvm use 18`), then `npm install && npm run dev` works as a standard Next.js app on `http://localhost:3000`. The sandbox stubs `better-sqlite3` only for build-check purposes — customer apps need the real package.

**Known deviation (not a bug):**
- Developer generated `PUT /api/tasks/:id/complete` instead of `PATCH /api/tasks/:id`. Functionally correct; the benchmark's keyword evaluator still passes. Worth noting for a future Developer prompt tightening pass.

---

## Recently Shipped (for short-term context — prune after a few weeks)

- **Pipeline Refactor v0.2.0** (merged 2026-05-03, tag `v0.2.0-pipeline-refactor`) — 6-phase refactor: state-machine handler registry, API timeout + retry, `feature_id` threading, typed schema batch, `BUILD_CHECK` state, `CodePatch` patch-based revisions.
- **DDC v1** (merged 2026-05-03) — replaces conversational `CustomerConfig` with the 4D contract (Actor / DomainEntity / UseCase / BusinessRule + Relationships) enforcing referential integrity.
- **Build sandbox** (merged to `main` 2026-05-06) — pre-seeded `node_modules` + `better-sqlite3` stub + hardlink-per-run; cuts full build to ~16 s. Includes race condition fix for `PIPELINE_COMPLETE` / `save_output` ordering. `enable_full_build_check` now defaults `True`.
