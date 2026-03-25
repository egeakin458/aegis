# Phase 2: API Layer, SSE Streaming & SQLite Persistence

## Goal

Connect the pipeline engine (Phase 1) to the outside world. After Phase 2, a client can:
1. Submit a customer config via HTTP
2. Stream pipeline events in real time via SSE
3. Answer clarification questions mid-pipeline
4. Retrieve the final generated code output

---

## Architecture Decisions

### D1: Runner Lifecycle — RunnerManager singleton

**Problem:** PipelineRunner is a stateful in-memory object. The API needs to find the right runner across multiple HTTP requests (start → SSE → clarify → output).

**Decision:** A `RunnerManager` class holds active runners in a `dict[run_id, RunnerEntry]`. It creates runners, wires up event callbacks, and provides lookup by run_id.

**Why not just a global dict?** The manager encapsulates agent instantiation, queue creation, and cleanup logic. It's the single coordination point between the HTTP layer and the pipeline engine.

**Scope:** Single-customer system — no multi-tenancy, no auth. One pipeline at a time is the expected usage, but the manager supports concurrent runs by design (each has its own runner + queue).

### D2: Background Execution — asyncio.create_task

**Problem:** Pipeline runs take minutes (4 LLM calls minimum). The start endpoint must return immediately.

**Decision:** `asyncio.create_task(runner.run(config))` after the start endpoint creates the runner. NOT `BackgroundTasks` — that blocks the worker after response is sent and doesn't play well with long-running async work.

**The task stores its result/exception on the RunnerEntry so GET /status and GET /output can check completion.**

### D3: SSE Event Flow — asyncio.Queue + replay

**Problem:** Events are produced by the pipeline (in a background task) and consumed by the SSE endpoint (a separate HTTP request). These are decoupled in time — the client may connect before, during, or after the pipeline runs.

**Decision:** Each RunnerEntry has an `asyncio.Queue`. The emit_event callback does two things:
1. Persists the event to SQLite (durable log)
2. Puts the event on the queue (live streaming)

The SSE endpoint:
1. Replays all existing events from the PipelineRun's event list (for events emitted before connect)
2. Then reads from the queue for new events (live stream)
3. Stops when it sees a terminal event (PIPELINE_COMPLETE or PIPELINE_FAILED)

**Reconnection:** If a client disconnects and reconnects, it gets a full replay from the event list. This is simple and sufficient for a prototype. (A production system would use `Last-Event-Id` header for incremental replay.)

### D4: SQLite Schema — runs + events tables

**Problem:** Need durable storage for evaluation, debugging, and surviving SSE disconnects.

**Decision:** Two tables:
- `pipeline_runs`: run metadata (state, timestamps, token totals, outcome)
- `pipeline_events`: full event log (one row per PipelineEvent)

Customer config is stored as JSON in the runs table. Code output files go to the filesystem under `outputs/{run_id}/`.

**Why not store code in SQLite?** Code files can be large (50+ files, hundreds of KB). SQLite handles blobs poorly at scale, and filesystem storage makes it easy to zip and download.

### D5: Output Storage — filesystem + manifest

**Problem:** Need to serve generated code files to the frontend and provide a download.

**Decision:** When pipeline completes, write each CodeFile to `outputs/{run_id}/{file_path}` and create a `manifest.json` with metadata. GET /output returns the manifest. A future endpoint can serve a zip.

---

## New File Structure

```
backend/app/
├── api/
│   ├── __init__.py          (empty → will have router)
│   └── routes.py            NEW: 5 API endpoints
├── db/
│   ├── __init__.py          (empty → stays empty)
│   ├── database.py          NEW: async SQLite connection + schema init
│   └── repositories.py      NEW: CRUD for runs and events
├── pipeline/
│   ├── __init__.py          (existing)
│   ├── runner.py            (existing, NO CHANGES)
│   ├── manager.py           NEW: RunnerManager + RunnerEntry
│   └── output_storage.py    NEW: write code files to disk
├── main.py                  MODIFIED: register router + startup/shutdown hooks
├── config.py                (existing, NO CHANGES — already has database_path, output_dir)
└── schemas/                 (existing, NO CHANGES — schemas are sufficient)
```

---

## Implementation Tasks

### Task 1: SQLite Layer (`app/db/`)

**Files:** `app/db/database.py`, `app/db/repositories.py`

**database.py — Connection management:**
```python
# Key interface:
async def init_db() -> None           # Create tables if not exist
async def get_connection() -> aiosqlite.Connection
async def close_db() -> None
```

**Schema (CREATE TABLE statements):**
```sql
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,           -- ISO-8601
    completed_at TEXT,
    state TEXT NOT NULL DEFAULT 'intake',
    outcome TEXT,                        -- success | partial | failed | NULL
    customer_config_json TEXT NOT NULL,
    total_input_tokens INTEGER DEFAULT 0,
    total_output_tokens INTEGER DEFAULT 0,
    feedback_cycles_json TEXT DEFAULT '{"code_revisions":0,"design_revisions":0}'
);

CREATE TABLE IF NOT EXISTS pipeline_events (
    event_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    agent TEXT NOT NULL,
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    data_json TEXT DEFAULT '{}',
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    duration_ms INTEGER,
    pipeline_state TEXT,
    FOREIGN KEY (run_id) REFERENCES pipeline_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_events_run_id ON pipeline_events(run_id);
```

**repositories.py — CRUD operations:**
```python
# Key interface:
async def save_run(run: PipelineRun, customer_config: CustomerConfig) -> None
async def update_run(run: PipelineRun) -> None
async def get_run(run_id: str) -> dict | None
async def save_event(event: PipelineEvent) -> None
async def get_events(run_id: str) -> list[dict]
```

**Testing notes:**
- Use an in-memory SQLite database (`:memory:`) for tests
- Test schema creation, insert, update, and query operations
- Test event ordering (ORDER BY timestamp)

**Estimated LOC:** ~120

---

### Task 2: Output Storage (`app/pipeline/output_storage.py`)

**Purpose:** Write CodeOutput files to disk when pipeline completes.

```python
# Key interface:
async def save_output(run_id: str, code_output: CodeOutput) -> Path
# Creates: outputs/{run_id}/{file.path} for each CodeFile
# Creates: outputs/{run_id}/manifest.json with metadata
# Returns: path to output directory
```

**manifest.json format:**
```json
{
    "run_id": "...",
    "project_name": "...",
    "created_at": "ISO-8601",
    "setup_instructions": "npm install && npm run dev",
    "features_implemented": ["..."],
    "files": [
        {"path": "app/page.js", "language": "javascript", "description": "..."}
    ]
}
```

**Testing notes:**
- Use `tmp_path` fixture for filesystem isolation
- Verify file content matches CodeFile.content
- Verify manifest.json is valid and complete

**Estimated LOC:** ~60

---

### Task 3: Runner Manager (`app/pipeline/manager.py`)

**Purpose:** Bridge between HTTP layer and PipelineRunner.

**Data structure:**
```python
@dataclass
class RunnerEntry:
    runner: PipelineRunner
    run_id: str
    task: asyncio.Task              # The background task running the pipeline
    event_queue: asyncio.Queue      # SSE consumers read from this
    customer_config: CustomerConfig # Stored for DB persistence
    created_at: datetime
```

**RunnerManager interface:**
```python
class RunnerManager:
    async def start_run(self, config: CustomerConfig) -> str:
        # 1. Create agents dict (instantiate all 4 agents)
        # 2. Create event_queue
        # 3. Create emit_event callback that:
        #    a. Calls runner.emit_event (adds to PipelineRun.events)
        #    b. Persists to SQLite via repository
        #    c. Puts event on event_queue
        # 4. Create PipelineRunner with agents + emit callback
        # 5. Create RunnerEntry
        # 6. asyncio.create_task(runner.run(config))
        # 7. Save initial run to SQLite
        # 8. Return run_id

    async def resume_run(self, run_id: str, answers: dict) -> None:
        # 1. Find RunnerEntry by run_id
        # 2. Verify state is CLARIFICATION
        # 3. asyncio.create_task(runner.resume(answers))
        # 4. Update the background task reference

    def get_entry(self, run_id: str) -> RunnerEntry | None:
        # Lookup by run_id

    async def cleanup_completed(self, max_age_seconds: int = 3600) -> None:
        # Remove entries for runs that completed > max_age ago
```

**Critical detail — the emit callback:**

The PipelineRunner already calls `self.emit_event()` internally. But it also accepts an `emit_event` callback in the constructor. The callback passed to PipelineRunner does:
1. Persist to SQLite (async, but event emission is sync — need to handle this)
2. Put on the queue (sync-safe via `queue.put_nowait`)

**Problem:** PipelineRunner's `emit_event` method is synchronous (it calls `self._emit(event)`), but SQLite writes are async.

**Solution:** The callback uses `asyncio.create_task` to fire-and-forget the SQLite write, OR we make the emit callback synchronous and queue a batch write. Simplest approach: use `queue.put_nowait()` for the SSE queue (sync-safe), and have a separate consumer that reads from a persistence queue and writes to SQLite.

**Even simpler:** Since the pipeline itself is running in an async context, we can wrap the SQLite write in `asyncio.get_event_loop().create_task()`. The callback becomes:
```python
def make_emit_callback(entry, repo):
    def callback(event):
        entry.event_queue.put_nowait(event)
        asyncio.get_event_loop().create_task(repo.save_event(event))
    return callback
```

**Testing notes:**
- Mock the agents (they just need to be in the dict, actual LLM calls are mocked)
- Test start_run creates a RunnerEntry and returns run_id
- Test resume_run raises if not in CLARIFICATION state
- Test event_queue receives events
- Test cleanup removes old entries

**Estimated LOC:** ~130

---

### Task 4: API Routes (`app/api/routes.py`)

**5 endpoints on an APIRouter with prefix `/api/pipeline`:**

#### 4a. POST /api/pipeline/start

```python
@router.post("/start")
async def start_pipeline(config: CustomerConfig) -> dict:
    # Validates config via Pydantic (automatic)
    # Calls manager.start_run(config)
    # Returns {"run_id": "...", "status": "started"}
```

**Response:** 201 Created with `{"run_id": "...", "status": "started"}`
**Errors:** 422 if config validation fails (automatic from Pydantic)

#### 4b. GET /api/pipeline/{run_id}/events

```python
@router.get("/{run_id}/events")
async def stream_events(run_id: str) -> EventSourceResponse:
    # 1. Find RunnerEntry
    # 2. Create async generator:
    #    a. Yield existing events from runner.current_run.events (replay)
    #    b. Then yield from event_queue until terminal event
    # 3. Return EventSourceResponse(generator)
```

**Key:** Uses `sse-starlette`'s `EventSourceResponse`. Each event is sent as:
```
data: {"event_id":"...","run_id":"...","event_type":"agent_start",...}

```

**Edge cases:**
- Run not found → return events from SQLite if the run completed before manager cleanup
- Run already complete → replay all events, then close stream
- Client disconnect → generator is cancelled by Starlette, no cleanup needed

#### 4c. POST /api/pipeline/{run_id}/clarification

```python
@router.post("/{run_id}/clarification")
async def submit_clarification(run_id: str, answers: dict[str, str]) -> dict:
    # Calls manager.resume_run(run_id, answers)
    # Returns {"status": "resumed"}
```

**Response:** 200 OK with `{"status": "resumed"}`
**Errors:** 404 if run not found, 409 if not in CLARIFICATION state

#### 4d. GET /api/pipeline/{run_id}/status

```python
@router.get("/{run_id}/status")
async def get_status(run_id: str) -> dict:
    # Returns current state, outcome, token usage, feedback cycles
    # First checks in-memory runner, falls back to SQLite
```

**Response:** 200 OK with:
```json
{
    "run_id": "...",
    "state": "development",
    "outcome": null,
    "started_at": "ISO-8601",
    "completed_at": null,
    "total_tokens": {"input_tokens": 5000, "output_tokens": 2000},
    "feedback_cycles": {"code_revisions": 0, "design_revisions": 0}
}
```

#### 4e. GET /api/pipeline/{run_id}/output

```python
@router.get("/{run_id}/output")
async def get_output(run_id: str) -> dict:
    # Returns the manifest.json content + code files
    # Only available when state is COMPLETE
```

**Response:** 200 OK with manifest content
**Errors:** 404 if run not found, 409 if not complete

**Testing notes:**
- Use FastAPI's TestClient (httpx)
- Mock RunnerManager for unit tests
- Test each endpoint's happy path and error cases
- Test SSE streaming with a mock event generator

**Estimated LOC:** ~150

---

### Task 5: Wire Up (`app/main.py`)

**Changes to main.py:**
```python
# Add:
from contextlib import asynccontextmanager
from app.api.routes import router
from app.db.database import init_db, close_db
from app.pipeline.manager import runner_manager  # singleton

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    yield
    # Shutdown
    await close_db()

app = FastAPI(..., lifespan=lifespan)
app.include_router(router, prefix="/api/pipeline")
```

**Estimated LOC:** ~15 net change

---

### Task 6: Tests

**New test files:**

| File | What it tests | Approach |
|------|--------------|----------|
| `tests/test_database.py` | SQLite schema, CRUD operations | In-memory SQLite, pytest-asyncio |
| `tests/test_output_storage.py` | File writing, manifest creation | tmp_path fixture |
| `tests/test_manager.py` | RunnerManager lifecycle, event queue, cleanup | Mock agents, mock DB |
| `tests/test_api.py` | All 5 endpoints | httpx TestClient, mock RunnerManager |

**Key test scenarios:**

**test_database.py:**
- Schema creates tables correctly
- Save and retrieve a pipeline run
- Save and retrieve events in order
- Update run state and outcome
- Events foreign key constraint

**test_output_storage.py:**
- Creates directory structure
- Writes files with correct content
- Creates valid manifest.json
- Handles nested paths (e.g., `app/api/menu/route.js`)

**test_manager.py:**
- start_run returns a valid run_id
- start_run creates a background task
- Event callback puts events on the queue
- resume_run raises ValueError if not CLARIFICATION
- get_entry returns None for unknown run_id
- cleanup removes old completed entries

**test_api.py:**
- POST /start with valid config returns 201 + run_id
- POST /start with invalid config returns 422
- GET /events streams events and closes on completion
- GET /events returns 404 for unknown run_id
- POST /clarification with answers returns 200
- POST /clarification on non-CLARIFICATION run returns 409
- GET /status returns current state
- GET /status falls back to SQLite for completed runs
- GET /output returns manifest when complete
- GET /output returns 409 when not complete

**Estimated test count:** ~40-50 new tests

---

## Implementation Order

```
Task 1: SQLite Layer          ← foundation, no dependencies
    │
    ├── Task 2: Output Storage     ← independent of DB, can parallel
    │
    ▼
Task 3: Runner Manager        ← depends on Task 1 (DB persistence)
    │
    ▼
Task 4: API Routes             ← depends on Task 3 (manager) + Task 2 (output)
    │
    ▼
Task 5: Wire Up                ← depends on Task 4 (routes)
    │
    ▼
Task 6: Tests                  ← write alongside each task, full suite at end
```

**Parallelization opportunity:** Tasks 1 and 2 are independent and can be built simultaneously. Task 6 (tests) should be written incrementally — each task gets its tests before moving to the next.

---

## Risk Analysis

### Risk 1: Sync emit_event callback vs async SQLite writes
**Problem:** PipelineRunner calls `self._emit(event)` synchronously, but `aiosqlite` writes are async.
**Mitigation:** Use `asyncio.get_event_loop().create_task()` inside the callback to schedule the async write. This works because the callback is always called from within an async context (the pipeline's `run()` or `resume()` coroutine). Alternatively, accumulate events and batch-write them.
**Fallback:** If event loop issues arise, use a threading approach: `threading.Thread(target=sync_write)`.

### Risk 2: SSE client disconnects during pipeline run
**Problem:** The SSE generator is cancelled when the client disconnects. Events keep flowing to the queue but nobody reads them.
**Mitigation:** Queue is bounded (maxsize=1000 is generous). Events are persisted to SQLite regardless of SSE consumers. On reconnect, replay from the event list. If the queue fills up, `put_nowait` raises `QueueFull` — catch and log (the event is already in SQLite).

### Risk 3: Server restart loses in-memory runner state
**Problem:** If uvicorn restarts, all RunnerEntry objects are lost. In-progress pipelines cannot be resumed.
**Mitigation:** Acceptable for thesis prototype. The SQLite log persists the last known state. The frontend can detect this (GET /status returns the SQLite state, which won't update anymore). A "run failed due to server restart" is an edge case we document but don't solve.

### Risk 4: Race condition between start_run and SSE connect
**Problem:** Client calls POST /start, gets run_id, then immediately connects to GET /events. If the background task hasn't started yet, there are no events.
**Mitigation:** The SSE endpoint first replays existing events (may be empty), then blocks on the queue. The first event (PIPELINE_STARTED) will arrive shortly. The client sees a brief pause, then events start flowing. This is fine.

### Risk 5: PipelineRunner.resume() needs the same runner instance
**Problem:** The clarification flow requires the exact same PipelineRunner instance that was paused. If the manager loses it, the pipeline can't resume.
**Mitigation:** RunnerManager holds a strong reference. Cleanup only runs on completed/failed runs. A CLARIFICATION-state runner is never cleaned up. If the server restarts mid-clarification, the run is effectively lost (Risk 3).

### Risk 6: Large code output filesystem writes
**Problem:** Generated apps might have 30+ files with deep directory nesting.
**Mitigation:** `os.makedirs(exist_ok=True)` for nested paths. Use `pathlib.Path` for safe path construction. Sanitize file paths from CodeOutput to prevent directory traversal (e.g., reject paths starting with `/` or containing `..`).

---

## What Does NOT Change

| Component | Reason |
|-----------|--------|
| `app/pipeline/runner.py` | Already complete. Manager wraps it, doesn't modify it. |
| `app/agents/*.py` | Pipeline engine is decoupled from API layer. |
| `app/schemas/*.py` | All schemas needed for Phase 2 already exist. |
| `app/config.py` | Already has `database_path` and `output_dir`. |
| `tests/test_agents.py` | Agent tests are independent of API layer. |
| `tests/test_pipeline_runner.py` | Runner tests use direct method calls, not HTTP. |
| `tests/test_schemas.py` | Schema tests are independent. |
| `tests/test_integration.py` | Tests the engine directly, not via API. |

---

## Definition of Done

Phase 2 is complete when:

1. `curl -X POST localhost:8000/api/pipeline/start -H 'Content-Type: application/json' -d @config.json` returns a run_id
2. `curl -N localhost:8000/api/pipeline/{run_id}/events` streams SSE events in real time
3. If clarification is needed, events contain the questions, and `curl -X POST .../clarification -d '{"q1":"answer"}'` resumes the pipeline
4. `curl localhost:8000/api/pipeline/{run_id}/status` returns the current state at any point
5. `curl localhost:8000/api/pipeline/{run_id}/output` returns the generated code manifest when complete
6. All events are persisted in SQLite (verifiable via `sqlite3 aegis.db 'SELECT count(*) FROM pipeline_events'`)
7. All existing 254 tests still pass
8. New tests bring the total to ~300+

---

## Estimated Scope

| Component | New LOC | New Tests |
|-----------|---------|-----------|
| db/database.py | ~60 | ~8 |
| db/repositories.py | ~60 | ~10 |
| pipeline/output_storage.py | ~60 | ~6 |
| pipeline/manager.py | ~130 | ~10 |
| api/routes.py | ~150 | ~15 |
| main.py changes | ~15 | — |
| **Total** | **~475** | **~49** |
