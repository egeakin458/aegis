# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What Is Aegis

Aegis is a multi-agent AI pipeline that operates as a virtual software company. A non-technical user submits an intake form, and four AI agents (Requirements Analyst, Solution Architect, Developer, QA Reviewer) produce a full-stack web application through structured handoffs and feedback loops.

Senior thesis project — Izmir University of Economics, Computer Engineering.

## Active Refactor — `feat/pipeline-refactor`

The branch `feat/pipeline-refactor` (cut from `main` at `ec6e758`) is a major improvement to the development cycle. Full plan with rationale is in memory at:

```
~/.claude/projects/-home-ege-projects-aegis/memory/project_pipeline_refactor_plan.md
```

**7 Tier 1 items (priority order):**

1. **Build/syntax verification** — `build_checker.py` + `BUILD_CHECK` state between Developer and QA
2. **`feature_id` threading** — `FeatureRequest.feature_id` → `CodeOutput.features_implemented` → `QAReview.requirements_coverage` *(start here — schema foundation)*
3. **Patch-based revisions** — `CodePatch` schema; Developer returns patches on revision instead of full regeneration
4. **Typed structured schemas** — `DataRequirements.entities` and `TechnicalRequirements.user_roles` as typed lists
5. **Enforce `DataField.type` as `Literal[...]`** — canonical type enum, structure `DataModel.relationships`
6. **API timeout + retry** — `settings.api_timeout` in `BaseAgent._call_llm`, retry on `RateLimitError` / 5xx
7. **`PIPELINE_PARTIAL` outcome** — distinct event + disk write when revision cap hit instead of `PIPELINE_FAILED`

**Implementation order:** Start with #2 to stabilize schemas, then #1 (most invasive). Items #4 and #5 can be done in parallel with #2.

---

## Development Commands

### Backend (run from `backend/` with virtualenv active)

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in ANTHROPIC_API_KEY

uvicorn app.main:app --reload --port 8000

pytest tests/                                                              # all tests
pytest tests/test_schemas.py                                               # single file
pytest tests/test_schemas.py::TestCustomerConfig                           # single class
pytest tests/test_schemas.py::TestCustomerConfig::test_minimal_config      # single test
```

### Frontend (run from `frontend/`)

```bash
cd frontend
cp .env.example .env.local    # set NEXT_PUBLIC_API_URL=http://localhost:8000

npm run dev                   # http://localhost:3000
npm run build                 # type-check + production build
npm run lint                  # ESLint
npm test                      # Jest unit tests (mappers)
npx jest --testPathPattern="config.test"   # single test file

# Regenerate TypeScript types from live backend (backend must be running)
npm run gen:types
```

Dev harness (visual states without a real run): `http://localhost:3000/dev/entries`

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

## Frontend Architecture

The frontend (`frontend/`) is a Next.js 14 App Router app that consumes the backend SSE stream and renders a live pipeline dashboard.

### Key Data Flows

**Form → Backend**: `IntakeModal` (7 sections, react-hook-form + zod) → `lib/mappers/config.ts:mapFormToCustomerConfig()` → `POST /api/pipeline/start` → `run_id`. All enum conversions happen in the mapper (display strings like `"Clean & Minimal"` → backend values like `"clean_minimal"`).

**SSE → UI state**: `lib/api/sse.ts` wraps `@microsoft/fetch-event-source` (not native `EventSource` — needed for proper connection lifecycle). `lib/hooks/use-pipeline.ts` runs a `useReducer` that dedupes events by `event_id`, maps each `EventType` to a `ConsoleEntry`, and derives `OrbitPhase` from the stream. URL param `?run={id}` enables refresh-safe replay — on mount the hook opens SSE against the existing run; the backend replays all stored events; the reducer dedupes.

**Clarification pause/resume**: `CLARIFICATION_NEEDED` surfaces a `ClarificationCard` with a submittable form. Submit hits `POST /api/pipeline/{run_id}/clarification`. The SSE stream stays open throughout (backend pauses, does not close the stream).

**Output**: On `PIPELINE_COMPLETE`, the hook fetches `GET /api/pipeline/{run_id}/output` and populates the `OutputViewer` drawer. The manifest includes inline file content (written by `app/pipeline/output_storage.py`).

### Frontend Directory Map

```
frontend/
  app/
    page.tsx                  main page (TopBar + AgentOrbit + ConsolePane + IntakeModal)
    dev/entries/page.tsx      dev harness — every orbit phase + console entry variant
  components/
    agent-orbit/              SVG orbit with framer-motion animations (hero element)
      index.tsx               CANVAS=560, C=280, R=190 — derives node positions from C/R
      agent-node.tsx          r=30 nodes, double-pulse rings, per-node glow filter, readable labels
      arcs.tsx                ambient 60s idle rotation, emerald trail, comet+tail, strokeWidth=2
      center-panel.tsx        foreignObject + AnimatePresence crossfade on phase change
    console/entries/          10 entry-type components (agent-start → summary)
    intake-modal/
      sections/               7 form sections
      widgets/                SegmentedToggle, MultiSelectChips, TagInput, ColorPicker, FeatureList
    top-bar/                  StatusPill, StatusStrip
    output-viewer/            (Phase 5) file tree + content drawer
    ui/                       shadcn-generated primitives
  lib/
    types/ui.ts               OrbitPhase, ConsoleEntry union, PipelineState
    schemas/intake-form.ts    zod schema + IntakeFormValues type + defaults
    mappers/config.ts         mapFormToCustomerConfig() — all enum round-trips
    mappers/events.ts         (Phase 3) PipelineEvent → ConsoleEntry
    mappers/phase.ts          (Phase 3) event stream → OrbitPhase
    api/client.ts             (Phase 3) typed fetch wrappers
    api/sse.ts                (Phase 3) fetch-event-source wrapper
    hooks/use-pipeline.ts     (Phase 3) main reducer hook
    utils/format.ts           formatTokens, formatElapsed, formatRelativeTime
    utils/generated/schema.d.ts  openapi-typescript output (committed)
```

### AgentOrbit — Design Notes

The orbit is the **primary hero element**. Key design decisions:
- **Layout**: orbit column is `lg:flex-[0_0_560px]` with a faint radial cyan gradient background; hard border removed
- **Canvas**: 560×560 SVG, center (280,280), orbit radius 190
- **Nodes**: `r=30`, double-pulse rings on active/waiting (second ring delayed 0.6s), per-node `node-glow-{agent}` Gaussian filter when active, complete bg `#064e35` (distinguishable from idle `#1e293b`)
- **Arcs**: base stroke `#1e3a4a` at 2px; active arc `#22d3ee` fully opaque at 2.5px; emerald trail (`#10b981`, opacity 0.35) on completed segments; comet `r=5` with ghost tail `r=3 delay=0.15s`
- **Idle rotation**: `OrbitArcs` wraps arcs in `motion.g` that does a 60s 360° rotation when `activeSegment === null`, stops when pipeline runs
- **Center panel**: 65px frosted containment circle + `<foreignObject>` with `AnimatePresence` crossfade (0.25s) on every phase transition; subtitle 11px `#94a3b8`

### Intake Form — Pending Refactor

The current form (7 sections, `components/intake-modal/sections/`) has ~8 zod fields that don't exist in `CustomerConfig` and several structural mismatches with the research doc spec (`docs/Aegis_Research_Decisions_Plan.md` §4.4). Work needed:

- **Schema** (`lib/schemas/intake-form.ts`): remove orphaned fields, add `description`, `entities`, `has_existing_data`, `auth_required`, `user_roles`; consolidate split fields
- **Mapper** (`lib/mappers/config.ts`): remove workaround concatenations once schema is clean
- **Sections**: industry → Select dropdown; problem → single textarea; features → single priority list; data → TagInput + toggle; technical → add auth toggle + userRoles; timeline → remove projectName/budgetRange

### Design Tokens

All in `tailwind.config.ts` under `theme.extend.colors.aegis`:
`bg=#0f172a`, `accent=#22d3ee`, `amber=#f59e0b`, `emerald=#10b981`, `error=#ef4444`, `purple=#9333ea`, `indigo=#4f46e5`

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM | Anthropic Claude API (Sonnet 4.6 primary, Haiku 4.5 for validation) |
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
| `primary_model` | `claude-sonnet-4-6` | Main LLM for agents |
| `secondary_model` | `claude-haiku-4-5-20251001` | Validation/eval LLM |
| `max_tokens` | 8192 | Max output tokens per LLM call |
| `max_code_revision_cycles` | 2 | QA → Developer feedback cap |
| `max_design_revision_cycles` | 1 | QA → Architect feedback cap |
| `max_clarification_rounds` | 3 | RA clarification loop cap |
| `database_path` | `aegis.db` | SQLite file path |
| `output_dir` | `outputs` | Generated code output directory |
