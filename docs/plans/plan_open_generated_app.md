# PLAN — "Open generated app" button in OutputViewer

**Goal:** Add a one-click "Open app" button to the OutputViewer that runs the generated Next.js app on a local port and opens it in a new browser tab. User can stop it; only one app runs at a time.

**Written against:** `8b4dae2` (main).

**Mode:** PLAN.

**Backlog item:** "Deferred — One-click Open generated app button" (carried in `MEMORY.md`).

---

## Background

Today the OutputViewer has a `QuickstartPanel` that displays the three-command recipe (`cd`, `npm install`, `npm run dev`) and offers per-command copy buttons. Power users copy and paste; non-technical viewers (the primary persona Aegis exists for) are stuck. The "Open" button closes that gap.

**Architecture choice (signed off):** Local subprocess via new backend endpoint. Backend spawns `npm install` then `npm run dev -- -p <auto>`; returns the URL. Frontend opens the URL in a new tab. No Docker, no cloud sandbox.

**Lifecycle (signed off):** One running app at a time. New `/launch` first stops any prior running app. User can explicitly stop via UI.

**Scope guardrails:**
- Demo / single-user / single-machine context only. No multi-tenancy.
- Acceptable that this only works when Aegis runs locally — Railway / Vercel deployments won't have ports for ephemeral apps (already noted in STATUS).
- `npm install` is slow first time (~30–60 s, native better-sqlite3 compile). UI needs a clear loading state.

---

## Phase A — Backend launcher

### A1. New module: `backend/app/launcher/`

Create `backend/app/launcher/__init__.py` with a singleton `app_launcher` of class `AppLauncher`. State is module-global and in-memory; no DB persistence (acceptable since this is dev/demo).

`AppLauncher` exposes:
- `async def launch(run_id: str) -> LaunchStatus` — kills any prior process, validates `backend/outputs/{run_id}/` exists, runs `npm install` (skipped if `node_modules/` already present), then `npm run dev -- -p <port>` as a subprocess. Picks a free port starting at `3100`. Returns the new status.
- `async def stop() -> LaunchStatus` — SIGTERM the current PID if any. Returns the new status.
- `def status() -> LaunchStatus` — current state.
- `async def shutdown()` — called on app lifespan close; ensures no orphan.

State enum: `idle | installing | starting | running | stopping | error`.

`LaunchStatus` Pydantic model:
```python
class LaunchStatus(BaseModel):
    state: Literal["idle","installing","starting","running","stopping","error"]
    run_id: str | None = None
    port: int | None = None
    url: str | None = None  # f"http://localhost:{port}" when running
    pid: int | None = None
    started_at: str | None = None  # ISO timestamp
    error: str | None = None  # error message when state == error
```

**Subprocess details (deliberate split — important):**
- `npm install` (bounded, awaitable): `asyncio.create_subprocess_exec("npm", "install", cwd=..., stdout=PIPE, stderr=STDOUT, start_new_session=True)` then `await proc.wait()`. Keeps the event loop responsive during the 30–60 s native compile.
- `npm run dev` (long-running, not awaited): `subprocess.Popen([...], cwd=..., stdout=open(log,"ab"), stderr=STDOUT, start_new_session=True)`. Just stash the PID.
- `start_new_session=True` on **both** so the child becomes a session leader / process-group leader. Critical: `npm` spawns `next dev` as a grandchild, and a plain SIGTERM to `npm` does NOT propagate to `next`. Stop must use `os.killpg(os.getpgid(pid), SIGTERM)` to take down the whole group; otherwise `next dev` orphans and holds the port.
- "install completed" marker: check `node_modules/.package-lock.json` exists, not just `node_modules/`. A prior interrupted install leaves a half-populated tree.
- Combine stdout/stderr into `backend/outputs/{run_id}/.aegis-launcher.log` for debugging without streaming.
- "Ready" detection: poll `http://localhost:{port}` with `httpx` until 200 or 45 s timeout (after spawn).
- Stop sequence: SIGTERM the process group; if process still alive after 5 s, SIGKILL the group.

**Verify:**
```bash
python3 -c "from app.launcher import app_launcher; print(app_launcher.status())"
# Expected: state='idle', run_id=None, ...
```

**Commit:** `feat(launcher): AppLauncher singleton for generated-app subprocess`

---

### A2. API endpoints

Add to `backend/app/api/routes.py`:

| Method | Path | Returns |
|---|---|---|
| `POST` | `/api/pipeline/{run_id}/launch` | `LaunchStatus` (state IMMEDIATELY after request — usually `installing` or `starting`) |
| `POST` | `/api/pipeline/launch/stop` | `LaunchStatus` |
| `GET` | `/api/pipeline/launch/status` | `LaunchStatus` |

**Fire-and-poll model:** `/launch` returns immediately after kicking off the work as a background task (`asyncio.create_task`); the response carries `state="installing"` (or `"starting"` if node_modules is ready). Frontend polls `/launch/status` until terminal (`running` or `error`). This matches B2's polling pattern for transitional states and avoids a 60–90 s held HTTP connection.

Transitions inside the background task: `idle → installing → starting → running` (or `error` at any step). The launcher singleton owns the state transitions; endpoints just trigger them.

**Edge cases:**
- `run_id` doesn't exist → 404
- `npm install` fails → 502 with error in status
- Port acquisition fails after 10 attempts → 503

**Wire shutdown:** in `backend/app/main.py` lifespan, call `await app_launcher.shutdown()` to kill any orphan subprocess on backend stop.

**Verify:**
```bash
curl -s -X POST -H "Authorization: Bearer $API_KEY" http://localhost:8000/api/pipeline/launch/status | jq
# Expected: {"state":"idle", ...}
```

**Commit:** `feat(api): /launch + /launch/stop + /launch/status endpoints`

---

### A3. Unit tests

Add `backend/tests/test_launcher.py`:
- `test_launcher_idle_initially` — status before any launch.
- `test_launcher_rejects_unknown_run_id` — 404 path.
- `test_launcher_kills_prior_app_on_relaunch` — mock subprocess; verify SIGTERM sent to prior PID.
- `test_launcher_stop_idempotent` — stop when idle is a no-op.
- `test_launcher_status_endpoint` — happy path via httpx.AsyncClient.

Mocks: patch `subprocess.Popen` so no real `npm install` runs in CI.

**Verify:**
```bash
cd backend && pytest tests/test_launcher.py -q
```

**Commit:** `test(launcher): cover lifecycle, relaunch, stop idempotency`

---

## Phase B — Frontend integration

### B1. API client + types

`frontend/lib/types/api.ts`:
```ts
export type LaunchState =
  | 'idle' | 'installing' | 'starting' | 'running' | 'stopping' | 'error'

export interface LaunchStatus {
  state: LaunchState
  run_id: string | null
  port: number | null
  url: string | null
  pid: number | null
  started_at: string | null
  error: string | null
}
```

`frontend/lib/api/launcher.ts` (new):
- `async function launchApp(runId: string): Promise<LaunchStatus>`
- `async function stopApp(): Promise<LaunchStatus>`
- `async function getLaunchStatus(): Promise<LaunchStatus>`

Use the same Authorization-Bearer pattern as `frontend/lib/api/pipeline.ts`.

**Verify:** `npm run gen:types` regenerates from live backend (if applicable); manual `tsc --noEmit` clean.

**Commit:** `feat(frontend): launcher API client + types`

---

### B2. LaunchPanel component

`frontend/components/output-viewer/launch-panel.tsx` (new). Sits above the existing `QuickstartPanel`. Two states visually:

- **Idle / not running:** big "Open app" button. Click triggers `launchApp`, transitions to `installing` → `starting` → `running`, then `window.open(status.url, '_blank')` and shows "App running at :3100 · [Stop]".
- **Running:** shows URL link + Stop button. Stop calls `stopApp`, transitions to `stopping` → `idle`.

Status polled every 1 s while in transitional states (`installing`/`starting`/`stopping`); paused at terminal states.

Error state: red banner with the error message, "Try again" button → retries `launchApp`.

On mount: call `getLaunchStatus()`; if `state === 'running'` and `run_id === this.runId`, show running UI directly. Otherwise show Open button.

**Verify:** dev harness at `http://localhost:3000/dev/entries` doesn't include this — add a manual story page if needed, or test live.

**Commit:** `feat(output-viewer): LaunchPanel — open/stop generated app`

---

### B3. Wire LaunchPanel into OutputViewer

`frontend/components/output-viewer/index.tsx`: render `<LaunchPanel runId={runId} />` above `<QuickstartPanel />`. Keep QuickstartPanel as the documented manual fallback.

**Verify:**
- Open frontend, complete a pipeline run, navigate to OutputViewer.
- Click "Open app" — observe loading state, then new tab opens the generated app on a chosen port.
- Click "Stop" — confirm process ends (`ps aux | grep "next dev"` shows no aegis-launched process).
- Trigger a second pipeline run; click "Open app" from the second run — confirm the first was killed.

**Commit:** `feat(output-viewer): wire LaunchPanel into the viewer`

---

### B4. Frontend tests

Tests are limited (Jest in node env, no real browser). Add:
- `__tests__/components/launch-panel.test.tsx` — render in idle/running/error states with mocked API. Verify Stop button only shows in running, Try again only in error.
- Mock `window.open` and assert it's called with `status.url`.

**Verify:**
```bash
cd frontend && npm test
```

**Commit:** `test(launch-panel): cover idle/running/error renders + window.open`

---

## Phase C — Verify + STATUS

### C1. Manual E2E

1. From scratch: `rm -rf backend/outputs/d40f9c05* backend/outputs/68775867*` (keep some recent run).
2. Run benchmark_02 smoke; pipeline completes.
3. From frontend: open output viewer, click "Open app", wait for the generated app to load on `localhost:3100+`.
4. Verify the app works (load page, create a task, see it persist).
5. Click Stop; confirm process exits.
6. Run benchmark_02 again to produce a new `run_id`; click "Open app" on the new run; confirm first app's port is freed if reused.

### C2. STATUS update

- Remove the "Deferred" backlog item.
- Add to "Recently fixed":
  ```
  - **2026-05-27** — One-click "Open generated app" button in OutputViewer. New backend launcher (`backend/app/launcher/`) + endpoints (`POST /launch`, `POST /launch/stop`, `GET /launch/status`); new frontend `LaunchPanel` above the existing QuickstartPanel. One running app at a time. Subprocess killed on backend shutdown. Demo / single-machine only — Railway path stays manual.
  ```

**Commit:** `chore(status): close Open-generated-app deferred item`

---

## What can go wrong

| Symptom | Action |
|---|---|
| `npm install` exceeds 180 s timeout | First run is slow (~30–60 s native compile). 180 s budget allows for cold registry. If still slow, the host is missing `build-essential` / `python3` — surface as error with the launcher log path. |
| Port 3100 already taken by frontend or stale process | AppLauncher port-pick loop scans 3100..3199. If all taken, fail with clear error. |
| SIGTERM to `npm` doesn't kill `next` (orphan port holder) | Fixed by Phase A1's `start_new_session=True` + `os.killpg`. If still observed: re-check `os.getpgid(pid)` returns the expected group. |
| Backend crash leaves orphan `next dev` running | A1's shutdown hook should prevent. If it bypasses (SIGKILL on backend), user must `pkill -g <gid>` or `pkill -f "next dev"` manually. Document in STATUS. |
| Half-installed `node_modules/` triggers false "install complete" | Fixed by checking `node_modules/.package-lock.json` (npm writes this last). |
| Frontend polls forever in `installing` state | Polling has a max attempts cap. After 90 s, transition to `error` with "install timed out" message. |
| Generated app fails to start (next dev errors) | Surface stderr from `.aegis-launcher.log` in the error state. Provide a "View log" link. |
| Two browsers click "Open app" at the same time | Single-customer system, not a real concern. Last-write-wins on the launcher state. |

**Two-strike rule:** if any step fails twice after fixes, stop and surface.

---

## Contract Change Checklist

This is a feature add. The checklist:

1. ✅ **Pydantic schemas** — new `LaunchStatus` model in `app/schemas/` (or inline in launcher module).
2. ✅ **Zod / TS types** — new `LaunchStatus` + `LaunchState` in `frontend/lib/types/api.ts`. No Zod runtime validator needed (these don't come from agent output).
3. ❌ Agent prompts — not touched.
4. ❌ Frontend mappers — these are NOT SSE event payloads; they're REST responses. No new EventType.
5. ❌ Backend fixtures — not touched.
6. ❌ `manager.py` context dict — not touched (launcher is independent of pipeline runner).
7. ✅ STATUS.md updated.
8. ❌ Migration plan — no DB schema change.

Looks complete.

---

## Estimated time

- Phase A: ~60 min (launcher module + endpoints + tests)
- Phase B: ~45 min (API client + LaunchPanel + tests + wiring)
- Phase C: ~15 min (manual E2E + STATUS)

Total: ~2 hours wall, 6–8 commits.
