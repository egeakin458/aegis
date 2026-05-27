# STATUS

Live state. Competition day: **2026-05-16** (tomorrow).

288/288 unit tests pass. E2E smoke green on `benchmark_02_todo_ddc` (run `ab4f5a1e`, 2026-05-10) — 19 files generated, 100% feature/test score, 231.8 s wall.

---

## Current state

UI/UX audit items from 2026-05-11 are fully addressed (Day-1 through Day-5 fixes, plus 2026-05-15 polish). Pipeline is demo-ready:

- Quick path is green (no stray auth deps)
- Console uses amber for recoverable events, red only for terminal failure
- Idle orbit no longer drifts — arc/node alignment is stable
- Rich revision card shows severity-grouped issues, quality score, round pill
- Reconnect button in connection-lost pill
- Flow primer and echo-description cards on submit
- Feature status (Working / Not working) in final summary card
- Share link button in top bar
- Per-phase ETAs in status strip
- Auto-open intake on first visit; output viewer auto-selects first file
- ZIP quickstart panel in output viewer

**Remaining risk:** better-sqlite3 Node 22+ incompat (see Backlog #11). Demo machine must run Node 20 LTS.

---

## Smoke regression check

Run before any commit that touches agents, schemas, or the pipeline:

```bash
python evaluation/run_benchmark.py evaluation/benchmarks/benchmark_02_todo_ddc.json
```

Expected: `pipeline_complete`, 100% feature/test score, ~4 min wall.

---

## Code freeze

**2026-05-13** (passed). In rehearsal mode — no code changes unless a critical bug surfaces.

---

## Backlog (post-competition)

Top-level pipeline timeout (#6 — bounds worst-case hang at the pipeline level), Developer prompt PATCH tightening (#7), QA verdict consistency (#8), startup sweep (#9), `_sanitize_path` edge case (#10), **better-sqlite3 Node 22+ incompat** (#11 — agents emit `better-sqlite3@^9.6.0` which fails to compile on Node ≥22 due to V8 API changes; manual bump to `^11` was needed to launch the generated guestbook app on Node v24. Fix: update the Developer agent prompt's deps allowlist and/or `_ALLOWED_DEPS` in `build_checker.py` to pin `better-sqlite3@^11`. Pre-freeze workaround for the demo: ensure demo machine runs Node 20 LTS, or pre-stage the version bump in a docs note.).

---

## Recently fixed

- **2026-05-15** — **Amber palette for mid-pipeline events + rich revision card** (`da34652`). Red used to fire on every non-success event (validation retries, build-check failures, revisions), diluting the danger signal. Now: red = terminal failure only; amber = recoverable mid-pipeline events. Backend emits `REVISION_REQUESTED` with the full `QAReview` payload (verdict, `code_quality_score`, per-issue severity / affected file / suggestion, round X/Y). `RevisionRequestedEntry` rewritten: severity-grouped issue list, expandable per-issue suggestion, 5-dot quality score, Round X/Y pill, reassuring footer. Build-check failed card and file-generated `removed` action also shifted red→amber. 288/288 backend, 72/72 frontend, `tsc --noEmit` clean.
- **2026-05-15** — **Orbit idle rotation removed** (`16625aa`). The arcs `<motion.g>` rotated 360° over 60 s at idle, but agent nodes are drawn at fixed cardinal positions outside the group — alignment only holds at rotate=0. Any non-zero angle exposed visible gaps between arcs and nodes; on submit, framer-motion animated back over another 60 s, leaving the ring looking broken for up to a minute. Snapped to rotate=0 with duration=0. Idle aliveness retained via center-panel breathing and node pulse rings.
- **2026-05-11** — **Dev-mode SSE replay was dead**. `useEffect` in `use-pipeline.ts` opened SSE on mount but the cleanup closed it, and React 18 StrictMode's double-mount left the guard (`runId !== runIdRef.current`) preventing reopen — shareable `?run=<id>` links rendered an empty stage with "Connection lost". Fix: always (re)open SSE on remount; dispatch SET_RUN only on first attach. Production not affected (no double-mount). 72/72 frontend tests, `tsc --noEmit` clean. Surfaced while capturing per-phase screenshots of the guestbook benchmark (`docs/guestbook_screenshots/`, run `f4b4517a…`).
- **2026-05-11** — UX Day-5 polish landed. **#12** (Suspense fallback): replaced the black-rectangle fallback with a centered "Loading Aegis…" pulse. **#14** (default file in OutputViewer): viewer now auto-selects `README.md` → `app/page.js` → `app/page.jsx` → `app/page.tsx` → `package.json` → first file, so users see content immediately instead of a blank pane. **#18** (share link): top bar gained a "Share link" button (shown when a run is active) that copies `${origin}${pathname}?run=${runId}` to clipboard. **#17** (per-phase ETAs): added `phaseRemainingLabel()` returning per-phase estimates (RA ~3m, SA ~3m, Dev ~90s, build check ~50s, build-check-failed ~90s, QA ~40s, dev/sa revising 60–90s); shown in `StatusStrip` next to elapsed when active. 72/72 frontend tests, `tsc --noEmit` clean.
- **2026-05-11** — UX Day-4 fixes landed. **#10** (manual reconnect): `usePipeline` now exposes a `reconnect()` callback; `ConnectionLostPill` shows a "Reconnect" button when state is `disconnected`. **#11** (duplicate phase): dropped phase label from `StatusStrip` (was mangling "Ra Running" / "Sa Running"); orbit center + `StatusPill` remain authoritative. **#13** (Quick-mode Back): the permanently-disabled Back button is now hidden in Quick mode (still rendered in Structured mode where it works). **#19** (orbit center wrap): widened `foreignObject` 150→180 and shortened idle copy to "Start with the intake form" — fits one line. 72/72 frontend tests, `tsc --noEmit` clean.
- **2026-05-11** — UX Day-3 fixes landed. **#5** (soften build-check failure): `BuildCheckCard` now appends "The agents will review these and try again — no action needed on your side." beneath failure issue lists. **#6** (flow primer): new `FlowPrimerCard` is dispatched alongside `CONFIG_SUBMITTED` showing the 4-step pipeline (Requirements → Design → Build → Review, ~4 min) so first-time viewers know what's coming. **#7** (clarification context): `ClarificationCard` now reads "Your project analyst needs your input" with a "Paused" tag and an explainer "The pipeline is paused until you answer." **#8** (top-bar cleanup): "Start Over" removed from `TopBar`; "New Project" now confirms mid-flight (not in idle/complete/error) before abandoning the run and resets state via `resetRun`. **#9** (free-text examples): `FreeTextSection` gained three one-click example prefills (Todo list / Inventory tracker / Event RSVP) via `setValue`. **G** (partial-build next action): backend `_finalize_run` now joins `qa_review.requirements_coverage` with DDC `use_case.name` and attaches `feature_status` to `pipeline_complete`/`pipeline_partial` event data; frontend `SummaryCard` renders grouped "Working ({n})" / "Not working ({n})" lists with QA evidence. 288/288 backend tests, 72/72 frontend tests, `tsc --noEmit` clean.
- **2026-05-11** — UX Day-2 fixes landed. **#4** (idle CTA): `IntakeModal` auto-opens when there is no `?run=` param — first-time viewers see the form, not an empty stage. **E** (echo description): new `ConfigSubmittedCard` is prepended to the console on `startRun` with the project name + submitted description, giving the viewer an anchor for "is the AI building what I asked for?". **F** (collapse file rows): consecutive `file-generated` entries from the same agent are grouped in `ConsolePane` into a single `FileGeneratedGroup` ("Developer wrote N files", expandable on click) — no more wall of "Updated:" rows. **#3** (ZIP quickstart): new `QuickstartPanel` inside `OutputViewer` shows the three-command launch recipe (cd / npm install / npm run dev -- -p 3100) with per-command and copy-all buttons. 72/72 frontend tests, `tsc --noEmit` clean.
- **2026-05-11** — UX Day-1 fixes landed. **Fix C** (Quick-path green): RA system prompt now forbids introducing auth actors/use cases unless the description explicitly mentions identity — smoke-verified end-to-end on "personal task manager" Quick description (`pipeline_complete`, 0 revisions, no `bcryptjs`/`jose` in deps). **Fix A**: `base.py` retry path no longer leaks raw `ValidationError` into the user-facing console — friendly message "<agent>'s draft didn't validate; retrying."; raw error goes to backend `logger.warning` only. **Fix #2**: `startPipeline` / `submitClarification` failures now surface as a terminal `ErrorCard` in the console (with a 401-specific hint pointing at `NEXT_PUBLIC_API_KEY`), no more silent dead-end. **Fix #1**: `ErrorCard` "Start Over" now wired to `resetRun` (threaded via prop through `ConsolePane`); "View Logs" removed. Structured DDC smoke still 100/100. 288/288 backend tests, 72/72 frontend tests.
- **2026-05-10** — `api_timeout` 120 s → 600 s. Developer call measured at 111.5 s on a simple DDC; was running with 7 % headroom under the SDK timeout. Now 5×.
- **2026-05-10** — `evaluation/run_benchmark.py` sends `Authorization: Bearer` header. Was 401-ing against an auth-enabled backend.
- **2026-05-10** — SSE handler dedupes by `event_id` across replay/queue boundary. Early events (e.g. `PIPELINE_STARTED`) were yielded twice; frontend was masking it via its own dedupe.
