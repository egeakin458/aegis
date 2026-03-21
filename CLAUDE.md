# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What Is Aegis
Aegis is a B2B virtual software company powered by a multi-agent AI pipeline. A non-technical business user fills out an intake form describing what they need, and Aegis's agent pipeline handles requirements gathering, solution design, implementation, and quality review — producing a full-stack web application.

This is a senior thesis project (Izmir University of Economics, Computer Engineering). The goal is a working, demonstrable product deployed to a beta group (student + supervisor) by Week 16.

## Development Commands

All commands run from `backend/` with the virtualenv active.

```bash
# Setup
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env       # then fill in ANTHROPIC_API_KEY

# Run dev server
uvicorn app.main:app --reload --port 8000

# Run all tests
pytest tests/

# Run a single test file
pytest tests/test_schemas.py

# Run a single test class or function
pytest tests/test_schemas.py::TestCustomerConfig
pytest tests/test_schemas.py::TestCustomerConfig::test_minimal_config
```

## Architecture Summary

**4 agents in a linear pipeline with feedback loops:**
1. **Requirements Analyst** — Analyzes raw `CustomerConfig`, runs clarification loop (max 3 rounds), outputs `FinalizedConfig`
2. **Solution Architect** — Receives `FinalizedConfig`, produces `TechnicalDesign` (data models, API specs, UI components, file structure)
3. **Developer** — Receives `FinalizedConfig` + `TechnicalDesign`, produces `CodeOutput` (complete code files forming a runnable project)
4. **QA Reviewer** — Receives all upstream outputs, outputs `QAReview` with verdict: `approve | revise_code | revise_design`

**Schema data flow:**
```
CustomerConfig → RA → FinalizedConfig → SA → TechnicalDesign → Dev → CodeOutput → QA → QAReview
                                                                                        ↓
                                                                          verdict: approve → done
                                                                          verdict: revise_code → Dev (max 2 cycles)
                                                                          verdict: revise_design → SA (max 1 cycle)
```

**Default pipeline path:** RA → SA → Dev → QA → Output

**Context passing — each agent receives:**
- **Solution Architect**: full `FinalizedConfig`
- **Developer**: full `FinalizedConfig` + `TechnicalDesign` (RA output is summarized into the design)
- **QA Reviewer**: full `FinalizedConfig` + `TechnicalDesign` (as reference) + `CodeOutput`

## Tech Stack
| Layer | Technology |
|-------|-----------|
| LLM API | Anthropic Claude API (Sonnet 4.5 primary, Haiku 4.5 for validation/eval) |
| Backend | Python 3.12 + FastAPI |
| Real-time | Server-Sent Events (SSE) via sse-starlette |
| Frontend | Next.js 14+ (App Router) + Tailwind CSS + shadcn/ui |
| Database | SQLite (state + logs) + filesystem (code artifacts) |
| Validation | Pydantic v2 for all inter-agent message schemas |
| Deployment | Railway (backend) + Vercel (frontend) |

## Key Constraints
- **Single-customer system** — no auth, no multi-user, one pipeline run at a time
- **All inter-agent communication uses structured JSON** validated by Pydantic schemas
- **Every agent output MUST be validated** against its Pydantic schema before being passed downstream
- **Every pipeline event MUST be logged** to SQLite with timestamp, agent, event type, token usage, duration
- **The observation UI is a core feature** — events must be emitted in business-friendly language, not raw logs
- **The customer intake form is the mandatory entry point** — no pipeline runs without a validated config
- **Custom orchestration only** — do NOT use LangChain, CrewAI, AutoGen, or any agent framework (the orchestration layer is the thesis's core intellectual contribution)

## How Agents Work

`BaseAgent` (`app/agents/base.py`) handles all LLM calls. Subclasses only implement `build_user_prompt(context: dict) -> str`. The base class:
1. Emits `AGENT_START` event
2. Calls LLM via `anthropic.AsyncAnthropic`
3. Strips markdown fences from response, then parses JSON and validates with Pydantic
4. On `ValidationError`: re-prompts **once** with the error message appended; raises `ValueError` if still invalid
5. Emits `VALIDATION_PASSED` or `ERROR` event with token counts and duration

**Creating a new agent subclass:**
```python
class MyAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name=AgentName.MY_AGENT,
            system_prompt="...",
            output_schema=MyOutputModel,  # Pydantic model
        )

    def build_user_prompt(self, context: dict[str, Any]) -> str:
        # Build user message from pipeline context
        return "..."
```

The `execute()` method signature: `async execute(context, run_id, emit_event) -> BaseModel`
- `context`: dict with upstream agent outputs
- `run_id`: pipeline run UUID string
- `emit_event`: callback `Callable[[PipelineEvent], None]`

All settings come from `app/config.py` via `pydantic-settings` (loaded from `.env`). Import the singleton: `from app.config import settings`.

## Agent System Prompt Structure
```
[IDENTITY] You are the {Role Name} at Aegis, a virtual software company.
[RESPONSIBILITY] Your job is to {task}. You receive {input} and produce {output}.
[CONSTRAINTS] You must NOT {boundaries}. You must ALWAYS {mandatory behaviors}.
[OUTPUT FORMAT] Your response must be valid JSON matching this exact schema: {schema}
[CONTEXT] Customer project: {config}. Previous agent output: {upstream}.
[TASK] Analyze the above and produce your output now.
```

## Pipeline Event Format
All events emitted to the frontend follow the `PipelineEvent` schema (`app/schemas/pipeline_events.py`):
```json
{
  "event_id": "uuid",
  "run_id": "uuid",
  "timestamp": "ISO-8601",
  "agent": "requirements_analyst | solution_architect | developer | qa_reviewer | system",
  "event_type": "agent_start | agent_complete | clarification_needed | llm_call | error | pipeline_complete",
  "message": "Human-readable business-language message for the UI",
  "data": {},
  "tokens_used": { "input": 0, "output": 0 },
  "duration_ms": 0
}
```

## Evaluation Framework
The `app/schemas/evaluation.py` schemas and `evaluation/benchmarks/` directory support thesis evaluation:
- **BenchmarkTask**: Predefined customer configs at 3 complexity tiers (simple/medium/complex)
- **LLM-as-judge**: `JudgeScore` with 3 independent scoring runs per task, averaged for reliability
- **BetaFeedback**: Structured survey from beta testers (student + supervisor)

## Important Implementation Notes
- Use `anthropic` Python SDK for all LLM calls — do NOT use LangChain, CrewAI, or any framework
- The PipelineRunner is a simple state machine (~300-500 LOC), not a complex framework
- SSE uses `sse-starlette`; the frontend uses native `EventSource` API
- SQLite via Python's built-in `sqlite3` module (plus `aiosqlite` for async) — no ORM
- All secrets go in `.env` (gitignored), never hardcoded
- All schemas are re-exported from `app/schemas/__init__.py` for clean imports

## Current Phase
**Phase 1: Core Pipeline Engine (Weeks 4-5)**
- [x] Project skeleton created
- [x] Pydantic schemas defined
- [x] Foundation verified (all fixes applied, 28 tests passing)
- [x] Agent base class
- [x] Requirements Analyst agent
- [x] Solution Architect agent
- [x] Developer agent
- [x] QA Reviewer agent
- [x] PipelineRunner state machine
- [x] Integration test (full pipeline from config to output, 254 tests passing)
