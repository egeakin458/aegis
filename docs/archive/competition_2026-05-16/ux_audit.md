# Aegis Frontend UX Audit — 2026-05-11

Scope: STATUS.md problem #2 — "a non-technical viewer can submit, watch, and download an app without a guide."

Method:
1. Static code read of `frontend/` covering intake → orbit → clarification → completion → output viewer.
2. **Live walkthrough** with puppeteer: minimal todo intake via Quick (free-text) mode. Run `49cef920…`, ~12 min wall, ended in **`pipeline_partial`** (build-check failures exhausted revision budget on `bcryptjs`/`jose` deps not in the build sandbox).

Screenshots: `docs/ux_audit_screenshots/01_idle.png` through `12_output_viewer_file_open.png`.

---

## Live-walk evidence (new) — must read before triaging

The live walk produced findings the static read missed. They are P0 because the Quick‑mode path — the *exact* path a non‑technical viewer takes — surfaces them.

### A. Pydantic validation errors are rendered raw to the user
`docs/ux_audit_screenshots/09_midrun_3.png` (and `_5.png`) show the SA's retry-on-validation surfacing as a message card titled "Our architect is revising their output format…" with a multi-line dump:
```
5 validation errors for TechnicalDesign
sa_components -> 0 -> input_schema -> id
  Field required [type=missing, input_value={'name':...}, input_type=dict]
…
```
A non-technical viewer sees a stack-trace-shaped object inside a friendly-looking card. This is the strongest "what now?" trigger in the run.
**Fix:** in `app/agents/base.py` the retry path emits an MESSAGE event with the raw `ValidationError` string. Replace with: friendly summary ("The architect's draft didn't validate; trying again.") + collapse the raw text behind an "Engineer details" toggle, or drop it entirely. **Effort: 30 min.**

### B. Build-check failures speak to engineers, not viewers
`10_complete.png` shows the run's end state:
```
✗ BUILD CHECK FAILED   3 errors
ERROR package.json — Dependency 'bcryptjs' is not in the build sandbox.
  Remove it or extend backend/build_sandbox/package.json + rerun setup_build_sandbox.sh.
ERROR package.json — Dependency 'jose' is not in the build sandbox. …
ERROR taskmaster — 'next build' failed (exit 1). See build log for details.
```
A non-technical viewer is told to edit `backend/build_sandbox/package.json` and run a shell script. The "Built with caveats" summary card sits right beneath it with a cheerful "Your Application was partially built" message — directly contradicting the red ERROR block.
**Fix:** rewrite the dep-drift issue in user language (`"The Developer chose an extra library that isn't in our build cache. Falling back to a simpler implementation."`); never expose `setup_build_sandbox.sh` path. Better: extend the allowlist to include `bcryptjs` and `jose` (or coach Developer prompt to avoid them) so the demo path doesn't hit this. **Effort: 1–2 h.**

### C. The Quick intake demo path ends in `pipeline_partial`, not green
STATUS.md says the smoke test is green, but that's the *structured* DDC. The Quick path used by a non-technical viewer fed a minimal placeholder DDC → RA expanded with auth use cases → Developer reached for `bcryptjs`+`jose` → dep_drift → revision cycles exhausted → partial. This is the most likely demo outcome unless prevented.
**Fix:** either (a) extend `_ALLOWED_DEPS` to include `bcryptjs` + `jose` and rerun `setup_build_sandbox.sh --force`, or (b) constrain the Developer system prompt to use Web Crypto / cookie-only auth so it never picks those packages, or (c) constrain the RA system prompt for Quick-mode submissions to skip auth unless explicitly requested. Option (c) is cheapest and most demo-aligned. **Effort: 30 min.**

### D. Top-bar phase label is grammatically wrong
`05_ra_running.png` and `04_pipeline_started.png` show "Ra Running" / "Sa Running" in the top bar. `top-bar/index.tsx:27` does `phase.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase())` which mangles agent acronyms.
**Fix:** drop the StatusStrip phase (already shown by StatusPill and orbit center — see #11), or map phases to a curated label set. **Effort: 5 min.**

### E. Submitted description is never echoed back
After the user types their idea and clicks Start Pipeline, the description disappears. Nothing in the console shows what was submitted — the viewer has no anchor for "is the AI building what I asked for?"
**Fix:** prepend a `ConfigSubmittedCard` to the console showing project name + 1-line description summary. **Effort: 30 min.**

### F. The completion screen buries the failure under "Updated:" noise
`10_complete.png` shows ~20 "Updated:" file rows stacked, then a red BUILD CHECK FAILED block, then the "Built with caveats" CTA. No grouping, no per-agent collapsing. The wall of file events drowns the actionable bit.
**Fix:** collapse repeated file-generated events into a single "Developer wrote 27 files" row that expands on click. **Effort: 1 h.**

### G. "Built with caveats" gives the viewer no next action
The viewer sees "partially built" but doesn't know which features work, what's broken, or whether to download. Only CTA is "View File Tree" — opens to alphabetical tree with no README, no "try the working features".
**Fix:** when `pipeline_partial`, show a third line below the existing two: "Working: tasks, categories. Broken: login." Sourced from the QA review's per-feature status. **Effort: 1.5 h (needs to read QA verdict).**

### H. React warning on DialogClose ref
Console: `Warning: Function components cannot be given refs. … Check the render method of DialogClose.` Surfaces from the shadcn dialog. Not user-visible but noisy in dev. **Effort: 10 min** — wrap with `forwardRef`.

---

## P0 — Hard dead ends (fix before demo) — static + live

### 1. Error-card buttons do nothing
`components/console/entries/error-entry.tsx:18-23` — "Start Over" and "View Logs" have no `onClick`. On terminal pipeline failure the viewer is stranded with two non-functional buttons.
**Fix:** wire "Start Over" to `resetRun`; drop "View Logs" or point it at `?run=…`. **Effort: 15 min.**

### 2. `startPipeline` / `submitClarification` failures are silent
`lib/hooks/use-pipeline.ts:181, :193` — errors are `console.error`'d only. Live walk confirmed this matters: the frontend default `.env.local` shipped without `NEXT_PUBLIC_API_KEY`, so the first POST returned 401 silently — the modal closed and the page sat inert with no clue. I had to grep curl to find out.
**Fix:** add an error-banner reducer action; render as an `ErrorCard` in the console; also tell the user when 401 specifically (`"Backend rejected the request — check NEXT_PUBLIC_API_KEY."`). **Effort: 30 min.**

### 3. No "what to do with the ZIP" guidance
`components/output-viewer/index.tsx` — Download ZIP works, but nothing tells the viewer how to actually run the app (`npm install && npm run dev`). After download the demo dead-ends.
**Fix:** add a "Your app is ready" panel inside OutputViewer with the three-command quickstart and copy-to-clipboard. Optionally inject a README into the ZIP server-side. **Effort: 1 h.**

### 4. Idle screen has no on-canvas CTA
`01_idle.png`: empty stage, orbit reading "Ready / Submit the intake form to begin", console reading "Submit the intake form to start the pipeline." — but the only button ("New Project") is small and top-right. A first-time viewer searches for a CTA where the eye lands (center).
**Fix:** auto-open `IntakeModal` when no `?run=`, OR add a large primary CTA in the center panel during `phase==='idle'`. **Effort: 30 min.**

## P1 — Confusing states the viewer can't resolve

### 5. Build-check failure looks catastrophic
Confirmed live (`09_midrun_3.png`, `10_complete.png`). Add an explainer line: "The agents will fix these and retry — no action needed." Also relates to **B** above. **Effort: 20 min.**

### 6. No primer on the 4-agent flow
AgentStart cards announce "Requirements Analyst started" cold. Add a one-time pre-run banner: "Four agents run in sequence: Requirements → Design → Build → Review (~4 min)." **Effort: 45 min.**

### 7. Clarification card lacks context
`console/entries/clarification.tsx:22` — header is just "Clarification needed". Doesn't say *you* need to answer, that the pipeline is paused, or how many rounds remain. (Live walk did not trigger clarification — RA accepted the placeholder DDC. Confirm with a sparser intake later.) **Effort: 30 min.**

### 8. "Start Over" vs "New Project" ambiguity
`top-bar/index.tsx:33-46` — overlapping semantics, "Start Over" wipes state with no confirm. **Fix:** drop "Start Over"; make "New Project" prompt to confirm if a run is mid-flight. **Effort: 20 min.**

### 9. Free-text form gives too much rope
`intake-modal/sections/free-text.tsx:50-57` — placeholder "Describe what your app should do…" 50–1500 chars. Add 2–3 one-click examples ("Todo list", "Simple inventory", "Event RSVP") that prefill the field. **Effort: 1 h.**

### 10. Connection lost has no manual recovery
`components/connection-lost-pill.tsx` — just a pill. Add a reconnect button that re-invokes `connectSSE(runId)`. **Effort: 30 min.**

## P2 — Polish

### 11. Phase rendered three times
Top bar StatusStrip ("Sa Running"), StatusPill ("Designing Architecture"), orbit center ("Designing"). Keep only the orbit. **Effort: 15 min.**

### 12. `Suspense` fallback is a black rectangle (`app/page.tsx:81`). **Effort: 10 min.**

### 13. "Back" button permanently disabled in Quick mode (`intake-modal/index.tsx:185-189`). Hide it. Visible in `02_intake_modal_open.png`. **Effort: 5 min.**

### 14. OutputViewer doesn't tell you where to start. Default-select `README.md` or `app/page.tsx` on open. **Effort: 15 min.**

### 15. "File too large to preview" has no per-file download. `output-viewer/index.tsx:165`. **Effort: 1 h (needs backend route).**

### 16. No confirm on destructive "Start Over" (or drop it per #8). **Effort: 5 min.**

### 17. No progress estimate. Hardcode per-phase ETAs. **Effort: 45 min.**

### 18. No copy/share link for `?run=…`. **Effort: 20 min.**

### 19. Orbit center text wraps awkwardly. `01_idle.png` — "Submit the intake form to begin" wraps to 3 lines inside the 150px center panel. **Effort: 10 min** (wider foreignObject or shorter copy).

---

## Recommended sequence (5 days to GBYF)

- **Day 1 (today):** Live-walk P0 — **A** (raw Pydantic), **B** (engineer-language build errors), **C** (extend dep allowlist OR constrain Developer prompt), **2** (silent submit failure), **1** (dead error buttons). These remove the worst surprises on the most-likely demo path. ~3.5 h.
- **Day 2:** P0 #3 (ZIP guidance), #4 (idle CTA), live **E** (echo description), **F** (collapse file events). ~3 h.
- **Day 3:** P1 #5, #6, #7, #8, #9, **G** (partial-build next action). ~3 h.
- **Day 4:** P1 #10 + P2 #11, #13, #16, #19. ~1.5 h.
- **Day 5:** buffer / rehearsal. Skip #15 (backend work) and #17 (not blocking).

## What to verify before locking copy

- Clarification card with a sparse description (e.g. 50 chars). Live walk skipped it — RA was content with the placeholder.
- Behaviour when the user closes the tab mid-run and returns via the `?run=` link.
- Error path: kill backend mid-run and observe `ConnectionLostPill` behaviour. Currently no manual retry.
