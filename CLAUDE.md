# CLAUDE.md

Guidance for Claude Code working in this repo. Architectural truth only — for current work and branch state see `STATUS.md`. For the feature/fix workflow (PLAN / SPIKE / DEBUG modes + Contract Change Checklist) see `WORKFLOW.md`.

## What Is Aegis

Aegis is a multi-agent AI pipeline that operates as a virtual software company. A non-technical user submits an intake form; four AI agents (Requirements Analyst, Solution Architect, Developer, QA Reviewer) produce a full-stack web application through structured handoffs and feedback loops. Senior thesis project — Izmir University of Economics, Computer Engineering.

## Architecture

### Pipeline Data Flow

```
CustomerConfigV2 → RA → CustomerConfigV2 (finalized) → SA → TechnicalDesign → Dev → CodeOutput → BuildCheck → QA → QAReview
                                                                                                                    ↓
                                                                                                      approve → done
                                                                                                      revise_code → Dev (max 2 cycles)
                                                                                                      revise_design → SA (max 1 cycle)
```

### Three-Layer Architecture

**Layer 1 — Pipeline Engine** (`app/pipeline/runner.py`, `app/agents/`)
The `PipelineRunner` is a state-machine with a handler registry (~420 LOC). Each agent extends `BaseAgent`, which handles LLM calls, JSON parsing, Pydantic validation, and one retry-on-validation-failure. Subclasses only implement `build_user_prompt(context: dict) -> str`.

**Layer 2 — Lifecycle Management** (`app/pipeline/manager.py`)
`RunnerManager` (singleton at `runner_manager`) bridges HTTP and the pipeline engine. It holds active `RunnerEntry` objects (runner + asyncio.Queue + background task), wires event callbacks that persist to SQLite and push to SSE queues, and manages cleanup. Pipeline runs execute as `asyncio.create_task` background tasks.

**Layer 3 — API & Persistence** (`app/api/routes.py`, `app/db/`)
FastAPI routes under `/api/pipeline`. SSE via `sse-starlette`. SQLite via `aiosqlite` with two tables (`pipeline_runs`, `pipeline_events`). Generated code written to `outputs/{run_id}/` with a `manifest.json`.

### Pipeline State Machine

States: `INTAKE → REQUIREMENTS → [CLARIFICATION ↔ REQUIREMENTS] → DESIGN → DEVELOPMENT → BUILD_CHECK → REVIEW → COMPLETE`

Clarification uses a pause-and-resume pattern: pipeline transitions to `CLARIFICATION`, `PipelineRunner.run()` returns, and a later `POST /clarification` call triggers `runner.resume(answers)` which re-enters `_run_from_state(REQUIREMENTS)`.

Feedback loops after QA review:
- `revise_code` → `CODE_REVISION` → re-runs Developer with `previous_code` + `qa_review` in context (Phase 5: Developer returns `CodePatch` diffs on revisions, not full files) → back to `REVIEW`
- `revise_design` → `DESIGN_REVISION` → re-runs Architect with `previous_design` + `qa_review` → `DEVELOPMENT` → `REVIEW`

### Special Schema: RAOutput

The Requirements Analyst is unique — it uses `RAOutputDDC` (not `CustomerConfigV2` directly) as its output schema. `RAOutputDDC` has a `needs_clarification` discriminator: when true, it contains clarification questions; when false, it contains a finalized `CustomerConfigV2`. `PipelineRunner._run_requirements()` handles both branches.

### Event System

Events flow through two paths simultaneously:
1. **SSE queue** (`asyncio.Queue` on `RunnerEntry`) — consumed by the SSE endpoint
2. **SQLite** (`repo.save_event`) — fire-and-forget via `asyncio.create_task`

The SSE endpoint replays events already in `runner.current_run.events`, then blocks on the queue. Terminal events (`PIPELINE_COMPLETE`, `PIPELINE_FAILED`) close the stream. Keepalive pings every 30 s.

### Output Storage

On pipeline completion, `save_output()` writes each `CodeFile` to `outputs/{run_id}/{path}` and creates `manifest.json`. Path traversal is blocked via `_sanitize_path` (rejects `..` and absolute paths). The manifest includes inline file content — the frontend `OutputViewer` reads it directly.

### API Endpoints

All under prefix `/api/pipeline`:

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/start` | Submit `CustomerConfigV2` (DDC), returns `run_id` |
| GET | `/{run_id}/events` | SSE stream — replays existing events, then live stream |
| POST | `/{run_id}/clarification` | Submit answers to resume paused pipeline |
| GET | `/{run_id}/status` | Current state, tokens, feedback cycles |
| GET | `/{run_id}/output` | Generated code manifest (only when complete) |

### Key Singletons

- **App**: `app.main:app` — FastAPI instance with lifespan (init_db/close_db)
- **Settings**: `from app.config import settings` (pydantic-settings, `.env`-loaded)
- **RunnerManager**: `from app.pipeline.manager import runner_manager`
- **DB**: `from app.db.database import get_connection` (must call `init_db()` first)

## Schemas

Source of truth for all inter-agent contracts: `backend/app/schemas/`. Reference these files directly — do not duplicate field listings here.

- `customer_config_v2.py` — DDC v1 contract (`schema_version: "ddc-v1"`). 4D model: `Actor` / `DomainEntity` / `UseCase` / `BusinessRule` + `Relationship`. Referential integrity enforced by `model_validator(mode="after")` — actor/entity/rule IDs referenced elsewhere must exist. `use_case.id` is the `feature_id` threaded through `FeatureRequest → CodeOutput → QAReview`.
- `agent_outputs.py` — `RAOutputDDC`, `TechnicalDesign`, `CodeOutput`, `CodePatch`, `BuildCheckResult`, `QAReview`.
- Frontend mirror: `frontend/lib/schemas/ddc.ts` (Zod v4). Regenerate API types with `npm run gen:types` (backend must be running).

## Build Verification — Pre-Seeded Sandbox

Full `next build` runs against `backend/build_sandbox/`, a fixed pre-installed dep set. Per-run workdirs hardlink the sandbox `node_modules` into `backend/build_sandbox/_runs/{run_id}/` so `next build` runs in ~30 s with no `npm install` on the hot path. Gated by `enable_full_build_check`.

**One-time setup (after clone or after changing sandbox deps):**

```bash
bash backend/scripts/setup_build_sandbox.sh           # install + stub
bash backend/scripts/setup_build_sandbox.sh --force   # rebuild from scratch
```

The script installs deps with `--ignore-scripts` (skips native compilation) then **stubs `better-sqlite3`** by overwriting `node_modules/better-sqlite3/lib/index.js` with a no-op JS class — eliminates the native-compilation dependency. Only the build check sees the stub; customer deployments install the real package fresh.

**Dep allowlist:** `backend/app/pipeline/build_checker.py:_ALLOWED_DEPS`. Generated `package.json` declaring anything outside this set fails the lightweight check with a `dep_drift` issue. To add a dep: extend the allowlist, extend `backend/build_sandbox/package.json`, rerun `setup_build_sandbox.sh --force`.

**Boundary:** full build catches broken imports, wrong App Router export signatures, missing `"use client"`, JSX/Tailwind/PostCSS errors. It does NOT catch runtime SQL bugs (better-sqlite3 stubbed) or endpoint logic — those remain QA's responsibility.

## Frontend

Next.js 14 App Router app consuming the backend SSE stream. Located in `frontend/`.

**SSE → UI state**: `lib/api/sse.ts` wraps `@microsoft/fetch-event-source` (not native `EventSource` — needed for proper connection lifecycle). `lib/hooks/use-pipeline.ts` runs a `useReducer` that dedupes events by `event_id`, maps each `EventType` to a `ConsoleEntry`, and derives `OrbitPhase` from the stream. URL param `?run={id}` enables refresh-safe replay.

**Intake**: `IntakeModal` has a Quick/Advanced toggle persisted in `localStorage` under `aegis_intake_mode`. Quick uses `mapFreeTextToDDC()` (placeholder Actor/Entity/UseCase, RA expands). Advanced uses `mapFormToDDC()` with 5 sections via `useFieldArray`. Both produce `CustomerConfigV2`.

**Clarification pause/resume**: `CLARIFICATION_NEEDED` surfaces a `ClarificationCard`. Submit hits `POST /clarification`. SSE stream stays open throughout — backend pauses, does not close.

**Hero element**: `components/agent-orbit/` is the primary visual. SVG with framer-motion. Specifics (canvas dims, colors, animation timings) live in the component files themselves.

**Dev harness** (every orbit phase + console entry variant): `http://localhost:3000/dev/entries`.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM | Anthropic Claude API (Sonnet 4.6 primary, Haiku 4.5 secondary) |
| Backend | Python 3.12 + FastAPI |
| Real-time | SSE via sse-starlette |
| Frontend | Next.js 14 + Tailwind CSS + shadcn/ui |
| Database | SQLite via aiosqlite (async) — no ORM |
| Validation | Pydantic v2 |
| Deployment | Railway (backend) + Vercel (frontend) |

**Generated apps** always use: Next.js 14 App Router + Tailwind CSS + better-sqlite3 + JavaScript. Enforced in agent system prompts — agents must NOT choose alternatives.

## Key Constraints

- **Custom orchestration only** — do NOT use LangChain, CrewAI, AutoGen, or any agent framework. The orchestration layer is the thesis's core intellectual contribution.
- **Single-customer system** — no auth, no multi-user, one pipeline run at a time expected.
- **Inter-agent communication** — structured JSON validated by Pydantic schemas. No free-form prose between agents.
- **Every pipeline event** must be logged to SQLite and streamed via SSE in business-friendly language.
- **Fixed generated tech stack** — never let an agent pick alternatives.

## Configuration

All settings in `backend/app/config.py` via `pydantic-settings`, loaded from `.env`. Read the source for the authoritative list. Required: `ANTHROPIC_API_KEY`. Notable flags: `enable_full_build_check` (default `False`), `max_code_revision_cycles=2`, `max_design_revision_cycles=1`, `max_clarification_rounds=3`.

## Development

### Backend (run from `backend/` with venv active)

```bash
uvicorn app.main:app --reload --port 8000

pytest tests/                                                              # all
pytest tests/test_schemas.py                                               # one file
pytest tests/test_schemas_v2.py::TestCustomerConfigV2                      # one class
pytest tests/test_schemas_v2.py::TestCustomerConfigV2::test_minimal_config # one test
```

### Frontend (run from `frontend/`)

```bash
npm run dev                   # http://localhost:3000
npm run build                 # type-check + production build
npm test                      # Jest (use `npm test`, NOT `npx jest` — local jest version)
npm run gen:types             # regenerate types from live backend
```

## Testing Patterns

Tests live in `backend/tests/`. Key fixtures from `conftest.py`:

- **`mock_anthropic`** — patches `app.agents.base.anthropic.AsyncAnthropic` so no real API calls happen. Pair with `make_mock_response`:
  ```python
  def test_my_agent(mock_anthropic, make_mock_response):
      mock_anthropic.messages.create = AsyncMock(
          return_value=make_mock_response({"key": "value"})
      )
  ```
- **`captured_events`** — returns `(events_list, emit_callback)`. Pass the callback as `emit_event` to `agent.execute()`.
- **`ddc_ecommerce`** — complete `CustomerConfigV2` from `tests/fixtures/ddc_ecommerce.json`.
- **DB tests** — use `init_db(":memory:")`; call `close_db()` in teardown.
- **API tests** — `httpx.AsyncClient` against FastAPI's `app`; mock `runner_manager` methods.
- **Filesystem tests** — pytest's `tmp_path` + monkeypatch `settings.output_dir`.

**Frontend Jest gotcha**: tests run in **node** environment. `import type` causes Babel parse errors in test files — use regular `import`.
