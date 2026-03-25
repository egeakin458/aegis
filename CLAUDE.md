# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What Is Aegis

Aegis is a multi-agent AI pipeline that operates as a virtual software company. A non-technical user submits an intake form, and four AI agents (Requirements Analyst, Solution Architect, Developer, QA Reviewer) produce a full-stack web application through structured handoffs and feedback loops.

Senior thesis project — Izmir University of Economics, Computer Engineering.

## Development Commands

All commands run from `backend/` with the virtualenv active.

```bash
# Setup
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # fill in ANTHROPIC_API_KEY

# Dev server
uvicorn app.main:app --reload --port 8000

# Tests
pytest tests/                                              # all tests
pytest tests/test_schemas.py                               # single file
pytest tests/test_schemas.py::TestCustomerConfig            # single class
pytest tests/test_schemas.py::TestCustomerConfig::test_minimal_config  # single test
```

## Architecture

### Pipeline Data Flow

```
CustomerConfig → RA → FinalizedConfig → SA → TechnicalDesign → Dev → CodeOutput → QA → QAReview
                                                                                        ↓
                                                                          approve → done
                                                                          revise_code → Dev (max 2 cycles)
                                                                          revise_design → SA (max 1 cycle)
```

### Three-Layer Architecture

**Layer 1 — Pipeline Engine** (`app/pipeline/runner.py`, `app/agents/`)
The `PipelineRunner` is a state machine (~420 LOC) that orchestrates four agents. Each agent extends `BaseAgent`, which handles LLM calls, JSON parsing, Pydantic validation, and retry-on-validation-failure. Subclasses only implement `build_user_prompt(context: dict) -> str`.

**Layer 2 — Lifecycle Management** (`app/pipeline/manager.py`)
`RunnerManager` (singleton at `runner_manager`) bridges HTTP and the pipeline engine. It holds active `RunnerEntry` objects (runner + asyncio.Queue + background task), creates agents, wires event callbacks that persist to SQLite and push to SSE queues, and manages cleanup. Pipeline runs execute as `asyncio.create_task` background tasks.

**Layer 3 — API & Persistence** (`app/api/routes.py`, `app/db/`)
FastAPI routes under `/api/pipeline`. SSE streaming via `sse-starlette`. SQLite via `aiosqlite` with two tables (`pipeline_runs`, `pipeline_events`). Generated code written to `outputs/{run_id}/` with a `manifest.json`.

### API Endpoints

All under prefix `/api/pipeline`:

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/start` | Submit `CustomerConfig`, returns `run_id` |
| GET | `/{run_id}/events` | SSE stream — replays existing events, then live stream |
| POST | `/{run_id}/clarification` | Submit answers to resume paused pipeline |
| GET | `/{run_id}/status` | Current state, tokens, feedback cycles |
| GET | `/{run_id}/output` | Generated code manifest (only when complete) |

### Key Singletons and Entry Points

- **App**: `app.main:app` — FastAPI instance with lifespan (init_db/close_db)
- **Settings**: `from app.config import settings` — pydantic-settings loaded from `.env`
- **RunnerManager**: `from app.pipeline.manager import runner_manager`
- **DB connection**: `from app.db.database import get_connection` (must call `init_db()` first)

### Agent Execution Flow

`BaseAgent.execute(context, run_id, emit_event)`:
1. Calls `build_user_prompt(context)` (subclass method)
2. Emits `AGENT_START` event
3. Calls Claude API via `anthropic.AsyncAnthropic` with prompt caching on system prompt
4. Strips markdown fences, parses JSON, validates with Pydantic
5. On `ValidationError`: re-prompts **once** with the error appended
6. Emits `AGENT_COMPLETE` or `ERROR` event with token counts and duration

### Special Schema: RAOutput

The Requirements Analyst is unique — it uses `RAOutput` (not `FinalizedConfig` directly) as its output schema. `RAOutput` has a `needs_clarification` discriminator: when true, it contains questions; when false, it contains a `FinalizedConfig`. The `PipelineRunner._run_requirements()` method handles both branches.

### Pipeline State Machine

States: `INTAKE → REQUIREMENTS → [CLARIFICATION ↔ REQUIREMENTS] → DESIGN → DEVELOPMENT → REVIEW → COMPLETE`

Clarification uses a pause-and-resume pattern: the pipeline transitions to `CLARIFICATION` state, the `PipelineRunner.run()` returns, and a later `POST /clarification` call triggers `runner.resume(answers)` which re-enters `_run_from_state(REQUIREMENTS)`.

Feedback loops after QA review:
- `revise_code` → `CODE_REVISION` → re-runs Developer with `previous_code` + `qa_review` in context → back to `REVIEW`
- `revise_design` → `DESIGN_REVISION` → re-runs Architect with `previous_design` + `qa_review` → `DEVELOPMENT` → `REVIEW`

### Event System

Events flow through two paths simultaneously:
1. **SSE queue** (`asyncio.Queue` on `RunnerEntry`) — consumed by the SSE endpoint
2. **SQLite** (`repo.save_event`) — fire-and-forget via `asyncio.create_task`

The SSE endpoint replays events already in `runner.current_run.events`, then blocks on the queue. Terminal events (`PIPELINE_COMPLETE`, `PIPELINE_FAILED`) close the stream. Keepalive pings sent every 30s.

### Output Storage

On pipeline completion, `save_output()` writes each `CodeFile` to `outputs/{run_id}/{path}` and creates `manifest.json`. Path traversal is blocked (`_sanitize_path` rejects `..` and absolute paths).

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM | Anthropic Claude API (Sonnet 4.5 primary, Haiku 4.5 for validation) |
| Backend | Python 3.12 + FastAPI |
| Real-time | SSE via sse-starlette |
| Frontend | Next.js 14 + Tailwind CSS + shadcn/ui |
| Database | SQLite via aiosqlite (async) — no ORM |
| Validation | Pydantic v2 for all schemas |
| Deployment | Railway (backend) + Vercel (frontend) |

**Generated apps** always use: Next.js 14 (App Router) + Tailwind CSS + better-sqlite3 + JavaScript. This is enforced in agent system prompts — agents must NOT choose alternative frameworks.

## Key Constraints

- **Custom orchestration only** — do NOT use LangChain, CrewAI, AutoGen, or any agent framework. The orchestration layer is the thesis's core intellectual contribution.
- **Single-customer system** — no auth, no multi-user, one pipeline run at a time expected.
- **All inter-agent communication** uses structured JSON validated by Pydantic schemas.
- **Every pipeline event must be logged** to SQLite and streamed via SSE in business-friendly language.
- **Fixed generated app tech stack** — Next.js 14 App Router + Tailwind CSS + better-sqlite3. Never allow agents to choose alternatives.

## Testing Patterns

Tests live in `backend/tests/`. Key patterns from `conftest.py`:

**Mocking the Anthropic client** — `mock_anthropic` fixture patches `app.agents.base.anthropic.AsyncAnthropic` so no real API calls are made. Use with `make_mock_response` to build fake LLM responses:
```python
def test_my_agent(mock_anthropic, make_mock_response):
    mock_anthropic.messages.create = AsyncMock(
        return_value=make_mock_response({"key": "value"})
    )
```

**Capturing events** — `captured_events` fixture returns `(events_list, emit_callback)`. Pass the callback as `emit_event` to `agent.execute()`.

**Customer config fixtures** — `valid_customer_config` and `valid_finalized_config` provide minimal valid instances for testing.

**Database tests** — Use in-memory SQLite (`:memory:`) via `init_db(":memory:")`. Call `close_db()` in teardown.

**API tests** — Use `httpx.AsyncClient` with FastAPI's `app`. Mock `runner_manager` methods.

**Filesystem tests** — Use pytest's `tmp_path` fixture and monkeypatch `settings.output_dir`.

## Configuration

All settings in `app/config.py` via `pydantic-settings`, loaded from `.env`:

| Setting | Default | Purpose |
|---------|---------|---------|
| `anthropic_api_key` | (required) | Claude API key |
| `primary_model` | `claude-sonnet-4-5-20250514` | Main LLM for agents |
| `secondary_model` | `claude-haiku-4-5-20251001` | Validation/eval LLM |
| `max_tokens` | 8192 | Max output tokens per LLM call |
| `max_code_revision_cycles` | 2 | QA → Developer feedback cap |
| `max_design_revision_cycles` | 1 | QA → Architect feedback cap |
| `max_clarification_rounds` | 3 | RA clarification loop cap |
| `database_path` | `aegis.db` | SQLite file path |
| `output_dir` | `outputs` | Generated code output directory |
