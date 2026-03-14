# Aegis — Claude Code Project Context

## What Is Aegis
Aegis is a B2B virtual software company powered by a multi-agent AI pipeline. A non-technical business user fills out an intake form describing what they need, and Aegis's agent pipeline handles requirements gathering, solution design, implementation, and quality review — producing a full-stack web application.

This is a senior thesis project (Izmir University of Economics, Computer Engineering). The goal is a working, demonstrable product deployed to a beta group (student + supervisor) by Week 16.

## Architecture Summary
- **4 agents in a linear pipeline with feedback loops:**
  1. **Requirements Analyst** — Analyzes raw customer config, runs clarification loop, produces finalized requirements
  2. **Solution Architect** — Produces technical design (data models, API specs, component breakdown, file structure)
  3. **Developer** — Produces actual code files (full-stack web app)
  4. **QA Reviewer** — Reviews code against requirements + design, issues revision requests or approves
- **Feedback loops (cycle-capped):**
  - QA → Developer: max 2 revision cycles
  - QA → Architect: max 1 design revision cycle
- **Pipeline topology:** Linear with conditional backward edges. Default path: RA → SA → Dev → QA → Output.

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
- **Code quality matters** — the Aegis codebase itself must follow clean architecture, separation of concerns, proper documentation

## Folder Structure
```
aegis/
├── CLAUDE.md                    # This file — project context for Claude Code
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app entry point
│   │   ├── config.py            # Settings & environment variables
│   │   ├── schemas/             # Pydantic models for ALL data contracts
│   │   │   ├── __init__.py
│   │   │   ├── customer_config.py
│   │   │   ├── agent_outputs.py
│   │   │   ├── pipeline_events.py
│   │   │   └── evaluation.py
│   │   ├── agents/              # Agent implementations
│   │   │   ├── __init__.py
│   │   │   ├── base.py          # BaseAgent class
│   │   │   ├── requirements_analyst.py
│   │   │   ├── solution_architect.py
│   │   │   ├── developer.py
│   │   │   └── qa_reviewer.py
│   │   ├── pipeline/            # Orchestration engine
│   │   │   ├── __init__.py
│   │   │   └── runner.py        # PipelineRunner state machine
│   │   ├── api/                 # REST & SSE endpoints
│   │   │   ├── __init__.py
│   │   │   └── routes.py
│   │   └── db/                  # SQLite persistence
│   │       ├── __init__.py
│   │       └── database.py
│   ├── tests/
│   │   └── test_pipeline.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/                    # Next.js app (scaffold separately)
│   └── ...
├── evaluation/
│   ├── benchmarks/              # Pre-filled customer configs for testing
│   ├── scripts/                 # Evaluation runner scripts
│   └── results/                 # Evaluation output data
├── docs/
│   ├── architecture.md
│   └── Aegis_Research_Decisions_Plan.md
├── .gitignore
└── README.md
```

## Current Phase
**Phase 1: Core Pipeline Engine (Week 4-5)**
- [x] Project skeleton created
- [x] Pydantic schemas defined
- [x] Foundation verified (all fixes applied, 28 tests passing)
- [x] Agent base class
- [ ] Requirements Analyst agent
- [ ] Solution Architect agent
- [ ] Developer agent
- [ ] QA Reviewer agent
- [ ] PipelineRunner state machine
- [ ] Integration test (full pipeline from config to output)

## Agent System Prompt Structure
Every agent prompt follows this template:
```
[IDENTITY] You are the {Role Name} at Aegis, a virtual software company.
[RESPONSIBILITY] Your job is to {task}. You receive {input} and produce {output}.
[CONSTRAINTS] You must NOT {boundaries}. You must ALWAYS {mandatory behaviors}.
[OUTPUT FORMAT] Your response must be valid JSON matching this exact schema: {schema}
[CONTEXT] Customer project: {config}. Previous agent output: {upstream}.
[TASK] Analyze the above and produce your output now.
```

## Pipeline Event Format
All events emitted to the frontend follow the PipelineEvent schema:
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

## Important Implementation Notes
- Use `anthropic` Python SDK for all LLM calls — do NOT use LangChain, CrewAI, or any framework
- Agent outputs are validated with Pydantic; if validation fails, re-prompt the agent ONCE with the error
- The PipelineRunner is a simple state machine (~300-500 LOC), not a complex framework
- SSE uses `sse-starlette` library; the frontend uses native `EventSource` API
- All secrets go in `.env` (gitignored), never hardcoded
- SQLite via Python's built-in `sqlite3` module — no ORM needed for this scale
