
## Project Summary

Aegis is a multi-agent AI pipeline that acts as a virtual software company. A non-technical user describes what they need through an intake form, and four AI agents — Requirements Analyst, Solution Architect, Developer, and QA Reviewer — collaboratively produce a full-stack web application. The orchestration engine is built from scratch as the thesis's core contribution.

---

## Key Technical Decisions

1. **4-agent linear pipeline with feedback loops.** Agents follow the software development lifecycle: requirements → design → implementation → review. The QA Reviewer can send work back to the Developer (max 2 cycles) or Architect (max 1 cycle).

2. **Custom orchestration, no frameworks.** LangChain, CrewAI, and AutoGen were evaluated and rejected. The orchestration layer is a ~420-line Python state machine — full control over prompts, state, and events is essential for the thesis argument.

3. **Pydantic-enforced contracts.** Every agent output is validated against a strict schema before being passed downstream. This prevents cascading format errors, a major failure mode in multi-agent systems.

4. **Fixed output tech stack.** Generated applications always use Next.js 14 + Tailwind CSS + better-sqlite3 to eliminate framework variance and enable consistent evaluation.

---

## What Has Been Built (Phases 1 & 2)

### Pipeline Engine (Phase 1)
- **BaseAgent** class handling LLM calls, JSON parsing, validation, and retry logic
- **4 specialized agents** with role-specific system prompts and structured output schemas
- **PipelineRunner** state machine with 10 states, clarification pause/resume, and feedback loop management
- 254 tests passing

### API Layer & Persistence (Phase 2)
- **5 REST endpoints** for starting runs, streaming events (SSE), submitting clarifications, checking status, and retrieving output
- **SQLite database** for durable event logging and run state persistence
- **RunnerManager** bridging HTTP requests to the pipeline engine via background tasks
- **Output storage** writing generated code to disk with a manifest
- Codebase hardening pass: 25 fixes across error handling, security, async safety, and configuration
- **359 tests passing** total

### Current Metrics

| Metric | Value |
|--------|-------|
| Source code | ~2,860 lines across 14 modules |
| Test code | ~7,450 lines across 11 test files |
| Total tests | 359 (all passing) |
| API endpoints | 5 + health check |

---

## Next Steps

### Phase 3: Frontend (Next.js 14)
The backend is complete and API-ready. The next phase builds three screens:
- **Intake Form** — customer submits project requirements
- **Pipeline Observer** — live SSE-powered timeline showing agent activity in business-friendly language
- **Output Viewer** — browse and download the generated application

### Phase 4: Evaluation & Deployment
- Run benchmark tasks through Aegis and a single-prompt baseline
- LLM-as-judge scoring and beta tester feedback collection
- Deploy to Railway (backend) + Vercel (frontend) for beta access

---

## Architecture Diagram

```
┌───────────────────────────────────────────────────┐
│              Frontend (Next.js 14)                 │
│       Intake Form / Observer / Output Viewer       │
└────────────────────┬──────────────────────────────┘
                     │  REST + SSE
                     ▼
┌───────────────────────────────────────────────────┐
│              Backend (FastAPI)                      │
│                                                    │
│   API Layer ──► Runner Manager ──► SQLite DB       │
│                      │                             │
│                      ▼                             │
│              Pipeline Runner                       │
│             (state machine)                        │
│                      │                             │
│     ┌────────┬───────┼────────┬──────────┐        │
│     ▼        ▼       ▼        ▼          │        │
│    RA ───► SA ───► Dev ───► QA           │        │
│                     ▲        │           │        │
│                     │  revise │           │        │
│                     └────────┘           │        │
│                                    Output Storage  │
└────────────────────┬──────────────────────────────┘
                     │
                     ▼
          ┌─────────────────────┐
          │  Anthropic Claude   │
          │  API (Sonnet 4.5)   │
          └─────────────────────┘

RA = Requirements Analyst    SA = Solution Architect
Dev = Developer              QA = QA Reviewer
```
