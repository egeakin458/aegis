# STATUS

Live state. Post-competition (2026-05-16 has passed). **Graduation presentation upcoming: 2026-06-16** — see "Presentation prep" below.

E2E smoke green on `benchmark_02_todo_ddc` 2026-06-12 (run `9580333b`, post RA-prompt cleanup) — 23 files generated, 100% feature/test score, 356.2 s wall, 0 revisions, QA verdict approve (score 5). 302/302 unit tests pass.

---

## Current state

Pipeline is demo-ready as of competition. All pre-competition UX polish (Day-1 through Day-5 fixes from the 2026-05-11 audit, plus 2026-05-15 amber-palette + orbit-rotation fixes) shipped in commit `0a522bb`. Competition artifacts (poster, UML, screenshots, walkthrough scripts) archived under `docs/archive/competition_2026-05-16/` in commit `3e3f30b`.

No code freeze. Free to refactor, add features, address backlog.

No known compat risks carried over after 2026-05-27 cleanup. Backlog #11 (better-sqlite3 Node 22+ incompat) closed by pinning `^11.0.0` in the Developer prompt; generated apps now install cleanly on Node ≥22.

---

## Presentation prep — 2026-06-16

Two open operational items before demo day (not code work). Full risk analysis in the local-only `docs/codebase_analysis_2026-06-12.md`.

- [ ] **Pre-warm the launch target.** The first launch of a generated app runs `npm install` + native better-sqlite3 compile — measured ~95 s cold vs ~7 s warm. Click LaunchPanel (or `POST /api/pipeline/{run_id}/launch`) once on the demo run the day before, so the live click hits the warm path and any install failure surfaces in private. Candidate: fresh smoke output `backend/outputs/9580333b-…` (todo app).
- [ ] **Rehearse the `?run=` replay fallback.** A live run is 4–6 min of nondeterministic LLM calls (cf. run `d19ca8b5` burning all revision cycles on build failures). Backup plan: open `http://localhost:3000/?run=<completed-run-id>` — replays the full event stream instantly. **Constraint found 2026-06-12**: replay only renders while the run is still in backend memory; after a uvicorn restart the DB-replay SSE path serves raw rows the frontend doesn't parse. So verify the URL renders once, write it down, and don't restart the backend between rehearsal and demo.

Demo-day rules of thumb: one browser tab per live run (single SSE queue per run — a second tab splits the stream); demo the **todo** app, not guestbook (guestbook's Server Components hardcode `fetch('http://localhost:3000/...')` and 500 on launcher ports, see #7).

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
- **#7** — Developer prompt PATCH tightening. Phase 5 patch semantics work but the prompt occasionally produces ambiguous diffs. **Updated 2026-05-27**: also seeing the Developer exhaust `max_code_revision_cycles=2` on build_check failures (run `d19ca8b5` failed 3 build_checks back-to-back, never reached QA). Suggests the prompt could include more guardrails against dep drift / common build_check failure modes.
- **#9** — Startup sweep. Clean stale state on backend start (orphaned runs, half-written outputs).
- **#10** — `_sanitize_path` edge case in `save_output`. Specific edge case noted but not pinned down — needs reproducer.

**Closed:**
- ~~**Deferred: One-click "Open generated app" button**~~ — landed 2026-05-27 (commits `44312ed` → `af3e857`). New `app/launcher/` backend module (subprocess lifecycle: install → start → ready, one app at a time, killpg-based teardown) + three endpoints (`POST /{run_id}/launch`, `POST /launcher/stop`, `GET /launcher/state`) + new `LaunchPanel` frontend component sitting above QuickstartPanel. Single-machine demo only — Railway path stays manual. E2E verified: cold launch ~95 s, warm relaunch ~7 s, prior PID killed on relaunch, port freed on stop.
- ~~**#8** — QA verdict rubber-stamping~~ — refuted 2026-05-27. Wired `QA_REVIEW_COMPLETE` event with full QAReview payload (commit `3b4775e`) so verdicts are auditable. Ran 3 benchmarks: QA emitted verdicts of score **2** (revise_code, caught a critical `db.prepare` bug), **5** (approve, 2 suggestions), **5** (approve, 0 issues). Predeclared threshold "all 4–5 across 3 runs" not met; QA is calibrated. Wiring infrastructure stays — useful for future audits.
- ~~**#11** — better-sqlite3 Node 22+ incompat~~ — closed 2026-05-27 (commit `8fa87b3`). Developer prompt now pins `^11.0.0`; sandbox already on `11.1.2`. `_ALLOWED_DEPS` was already name-only so no change there. Note: build check does not enforce version pins today; if version drift becomes a recurring problem, add a version check to `build_checker.py` as a follow-up.

---

## Recently fixed

Pre-competition rehearsal-week work consolidated. For per-fix detail see commit `0a522bb` body and `git log --since=2026-05-10 --until=2026-05-16`.

- **2026-06-12** — **RA prompt ID-generation cleanup** (`b1fe00a`). Collapsed three contradictory drafts (incl. the literal "WAIT — re-read" paragraph) into one rule with unchanged semantics: preserve input ids, otherwise generate human-readable `act_`/`ent_`/`rule_`/`uc_`/`rel_` ids. Embedded example now uses real cross-references and validates against `CustomerConfigV2` (placeholders previously failed referential integrity). Smoke-verified: run `9580333b`, 100% score, 0 revisions, QA approve score 5.
- **2026-06-12** — Docs reorganization committed (`e66f20c`): poster + updated UML moved out of the competition archive into `docs/Poster/` and `docs/SystemDesignUml/`; thesis folders (meetingReports, GraduationReports) kept local-only via `.gitignore`. Benchmark result JSONs committed as evidence (`1984358`).

- **2026-05-27** — **One-click "Open generated app" button** landed (`44312ed` → `af3e857`). Backend `app/launcher/` subprocess manager + 3 endpoints; frontend `LaunchPanel` above the QuickstartPanel. Auto-opens generated app in a new tab on first transition to running. One app at a time; relaunch kills prior process group (advisor caught the npm-vs-next process-group split early). E2E verified: cold ~96 s, warm ~7 s, prior PID killed, port freed on stop. 302 backend + 77 frontend tests pass. **New finding (out of scope)**: the guestbook generated app does server-side `fetch('http://localhost:3000/...')` from its Server Components and 500s when run on any other port. Worth folding into Developer prompt tightening (#7).
- **2026-05-27** — **Backlog #8 refuted: QA is calibrated, not rubber-stamping**. Wired `QA_REVIEW_COMPLETE` event (commit `3b4775e`) to expose every QA verdict + `code_quality_score` in `pipeline_events.data_json`. Audited 3 benchmark runs: QA produced score=2 (revise, caught a critical bug), 5 (approve, 2 suggestions), 5 (approve, clean). No always-high pattern. Wiring infra stays for future audits.
- **2026-05-27** — **Backlog #11 closed: better-sqlite3 pinned to `^11.0.0`** in the Developer prompt (`8fa87b3`). Empirically agents had been fabricating versions per run (`^9.4.3`, `^9.6.0`, `^11.10.0`); `^9.x` fails to compile on Node ≥22. Smoke-verified on `benchmark_02_todo_ddc` (run `68775867`, 308.5 s wall, 100% score, 0 code revisions); emitted `package.json` confirmed `"better-sqlite3": "^11.0.0"`. Plan at `docs/plans/plan_pin_better_sqlite3.md`.
- **2026-05-27** — **E2E smoke re-verified green** on `benchmark_02_todo_ddc` (run `d40f9c05`, 284.8 s wall, 100% feature/test score, pre-pin baseline). Build check correctly caught Developer emitting `eslint` in `package.json` (not in `_ALLOWED_DEPS`); Developer fixed on revision 1; second build_check passed in 15.6 s. Side finding: QA agent's verdict + score aren't persisted to event payloads today, see Backlog #8.
- **2026-05-27** — Post-competition cleanup: shipped the 11-day-old uncommitted UX polish as a single `feat(demo)` commit (`0a522bb`); archived competition artifacts (poster, UML, screenshots, walkthrough scripts, root-level puppeteer deps) under `docs/archive/competition_2026-05-16/` (`3e3f30b`).
- **2026-05-15** — Amber palette for mid-pipeline events + rich revision card; orbit idle rotation removed (`0a522bb`, originally `da34652` / `16625aa`).
- **2026-05-11** — UX Day-1 → Day-5 fixes: Quick-path auth scope, validation-retry messaging, ErrorCard wiring, idle CTA, echo-description card, file-row grouping, ZIP quickstart panel, build-check softening, flow primer, clarification context, top-bar cleanup, free-text examples, feature_status in summary, manual reconnect, duplicate-phase fix, Quick-mode Back hidden, orbit center wrap, Suspense fallback, default file in OutputViewer, share link, per-phase ETAs (`0a522bb`).
- **2026-05-11** — Dev-mode SSE replay fix (React 18 StrictMode double-mount) (`0a522bb`).
- **2026-05-10** — `api_timeout` 120 s → 600 s; benchmark runner sends `Authorization: Bearer`; SSE dedupes by `event_id` across replay/queue boundary.
