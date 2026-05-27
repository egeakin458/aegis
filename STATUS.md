# STATUS

Live state. Post-competition (2026-05-16 has passed). Back in development mode.

288/288 unit tests pass at last verification (2026-05-15). E2E smoke last green on `benchmark_02_todo_ddc` (run `ab4f5a1e`, 2026-05-10) — 19 files generated, 100% feature/test score, 231.8 s wall. **Re-run the smoke before resuming feature work** — 12 days have elapsed since the last verified green run.

---

## Current state

Pipeline is demo-ready as of competition. All pre-competition UX polish (Day-1 through Day-5 fixes from the 2026-05-11 audit, plus 2026-05-15 amber-palette + orbit-rotation fixes) shipped in commit `0a522bb`. Competition artifacts (poster, UML, screenshots, walkthrough scripts) archived under `docs/archive/competition_2026-05-16/` in commit `3e3f30b`.

No code freeze. Free to refactor, add features, address backlog.

**Known risk carried over:** better-sqlite3 Node 22+ incompat (Backlog #11). Agents emit `better-sqlite3@^9.6.0`; generated apps fail to compile on Node ≥22. Workaround during competition was Node 20 LTS on the demo machine. **For continued dev** this should be fixed properly — bump the pin in the Developer agent prompt and `_ALLOWED_DEPS`.

---

## Smoke regression check

Run before any commit that touches agents, schemas, or the pipeline:

```bash
# Terminal 1 — from backend/, venv active
ENABLE_FULL_BUILD_CHECK=true uvicorn app.main:app --port 8000

# Terminal 2 — from repo root
python evaluation/run_benchmark.py evaluation/benchmarks/benchmark_02_todo_ddc.json
```

Expected: `pipeline_complete`, 100% feature/test score, ~4 min wall.

Three benchmarks available under `evaluation/benchmarks/`:
- `benchmark_01_*` (legacy)
- `benchmark_02_todo_ddc.json` — primary smoke
- `benchmark_03_guestbook_ddc.json` — secondary smoke (added 2026-05-15)

---

## Backlog

Carried from pre-competition. Numbering preserved for traceability.

- **#6** — Top-level pipeline timeout. Bounds worst-case hang at the pipeline level (not just per-agent). Today a stuck agent can pin a run indefinitely.
- **#7** — Developer prompt PATCH tightening. Phase 5 patch semantics work but the prompt occasionally produces ambiguous diffs.
- **#8** — QA verdict consistency. Investigate whether QA is rubber-stamping (suspected pattern of always-4-or-5 scores).
- **#9** — Startup sweep. Clean stale state on backend start (orphaned runs, half-written outputs).
- **#10** — `_sanitize_path` edge case in `save_output`. Specific edge case noted but not pinned down — needs reproducer.
- **#11** — better-sqlite3 Node 22+ incompat. Pin to `^11.0.0` in Developer prompt deps allowlist and in `backend/app/pipeline/build_checker.py:_ALLOWED_DEPS`. Also extend `backend/build_sandbox/package.json` and rerun `setup_build_sandbox.sh --force`.
- **Deferred** — One-click "Open generated app" button in frontend OutputViewer. Currently users must run the three-command launch recipe from the QuickstartPanel manually.

---

## Recently fixed

Pre-competition rehearsal-week work consolidated. For per-fix detail see commit `0a522bb` body and `git log --since=2026-05-10 --until=2026-05-16`.

- **2026-05-27** — Post-competition cleanup: shipped the 11-day-old uncommitted UX polish as a single `feat(demo)` commit (`0a522bb`); archived competition artifacts (poster, UML, screenshots, walkthrough scripts, root-level puppeteer deps) under `docs/archive/competition_2026-05-16/` (`3e3f30b`).
- **2026-05-15** — Amber palette for mid-pipeline events + rich revision card; orbit idle rotation removed (`0a522bb`, originally `da34652` / `16625aa`).
- **2026-05-11** — UX Day-1 → Day-5 fixes: Quick-path auth scope, validation-retry messaging, ErrorCard wiring, idle CTA, echo-description card, file-row grouping, ZIP quickstart panel, build-check softening, flow primer, clarification context, top-bar cleanup, free-text examples, feature_status in summary, manual reconnect, duplicate-phase fix, Quick-mode Back hidden, orbit center wrap, Suspense fallback, default file in OutputViewer, share link, per-phase ETAs (`0a522bb`).
- **2026-05-11** — Dev-mode SSE replay fix (React 18 StrictMode double-mount) (`0a522bb`).
- **2026-05-10** — `api_timeout` 120 s → 600 s; benchmark runner sends `Authorization: Bearer`; SSE dedupes by `event_id` across replay/queue boundary.
