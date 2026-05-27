# STATUS

Live state. Post-competition (2026-05-16 has passed). Back in development mode.

E2E smoke green on `benchmark_02_todo_ddc` 2026-05-27 (run `68775867`, post better-sqlite3 pin) — 20 files generated, 100% feature/test score, 308.5 s wall, 0 code revisions. 288/288 unit tests pass.

---

## Current state

Pipeline is demo-ready as of competition. All pre-competition UX polish (Day-1 through Day-5 fixes from the 2026-05-11 audit, plus 2026-05-15 amber-palette + orbit-rotation fixes) shipped in commit `0a522bb`. Competition artifacts (poster, UML, screenshots, walkthrough scripts) archived under `docs/archive/competition_2026-05-16/` in commit `3e3f30b`.

No code freeze. Free to refactor, add features, address backlog.

No known compat risks carried over after 2026-05-27 cleanup. Backlog #11 (better-sqlite3 Node 22+ incompat) closed by pinning `^11.0.0` in the Developer prompt; generated apps now install cleanly on Node ≥22.

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
- **#8** — QA verdict consistency. Investigate whether QA is rubber-stamping (suspected pattern of always-4-or-5 scores). **Blocker**: today the QA agent's verdict + `code_quality_score` are not persisted to `pipeline_events.data_json` — only the downstream action (`revision_started` or `pipeline_complete`) is visible. To run the audit, first wire the QA payload into the `agent_complete` event for `qa_reviewer`. Observed 2026-05-27 during smoke re-verification.
- **#9** — Startup sweep. Clean stale state on backend start (orphaned runs, half-written outputs).
- **#10** — `_sanitize_path` edge case in `save_output`. Specific edge case noted but not pinned down — needs reproducer.
- **Deferred** — One-click "Open generated app" button in frontend OutputViewer. Currently users must run the three-command launch recipe from the QuickstartPanel manually.

**Closed:**
- ~~**#11** — better-sqlite3 Node 22+ incompat~~ — closed 2026-05-27 (commit `8fa87b3`). Developer prompt now pins `^11.0.0`; sandbox already on `11.1.2`. `_ALLOWED_DEPS` was already name-only so no change there. Note: build check does not enforce version pins today; if version drift becomes a recurring problem, add a version check to `build_checker.py` as a follow-up.

---

## Recently fixed

Pre-competition rehearsal-week work consolidated. For per-fix detail see commit `0a522bb` body and `git log --since=2026-05-10 --until=2026-05-16`.

- **2026-05-27** — **Backlog #11 closed: better-sqlite3 pinned to `^11.0.0`** in the Developer prompt (`8fa87b3`). Empirically agents had been fabricating versions per run (`^9.4.3`, `^9.6.0`, `^11.10.0`); `^9.x` fails to compile on Node ≥22. Smoke-verified on `benchmark_02_todo_ddc` (run `68775867`, 308.5 s wall, 100% score, 0 code revisions); emitted `package.json` confirmed `"better-sqlite3": "^11.0.0"`. Plan at `docs/plans/plan_pin_better_sqlite3.md`.
- **2026-05-27** — **E2E smoke re-verified green** on `benchmark_02_todo_ddc` (run `d40f9c05`, 284.8 s wall, 100% feature/test score, pre-pin baseline). Build check correctly caught Developer emitting `eslint` in `package.json` (not in `_ALLOWED_DEPS`); Developer fixed on revision 1; second build_check passed in 15.6 s. Side finding: QA agent's verdict + score aren't persisted to event payloads today, see Backlog #8.
- **2026-05-27** — Post-competition cleanup: shipped the 11-day-old uncommitted UX polish as a single `feat(demo)` commit (`0a522bb`); archived competition artifacts (poster, UML, screenshots, walkthrough scripts, root-level puppeteer deps) under `docs/archive/competition_2026-05-16/` (`3e3f30b`).
- **2026-05-15** — Amber palette for mid-pipeline events + rich revision card; orbit idle rotation removed (`0a522bb`, originally `da34652` / `16625aa`).
- **2026-05-11** — UX Day-1 → Day-5 fixes: Quick-path auth scope, validation-retry messaging, ErrorCard wiring, idle CTA, echo-description card, file-row grouping, ZIP quickstart panel, build-check softening, flow primer, clarification context, top-bar cleanup, free-text examples, feature_status in summary, manual reconnect, duplicate-phase fix, Quick-mode Back hidden, orbit center wrap, Suspense fallback, default file in OutputViewer, share link, per-phase ETAs (`0a522bb`).
- **2026-05-11** — Dev-mode SSE replay fix (React 18 StrictMode double-mount) (`0a522bb`).
- **2026-05-10** — `api_timeout` 120 s → 600 s; benchmark runner sends `Authorization: Bearer`; SSE dedupes by `event_id` across replay/queue boundary.
