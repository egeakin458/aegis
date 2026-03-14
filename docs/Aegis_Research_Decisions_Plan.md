# Aegis — Research Findings, Technical Decisions & Implementation Plan

**Prepared for:** Hüseyin Ege Akın  
**Date:** March 14, 2026  
**Status:** Ready for student review and commitment

---

## PART 1 — Research Findings & Recommendations

### 4.1 Optimal Agent Structure & Pipeline Topology

**Recommendation: 4 agents in a linear pipeline with structured feedback loops.**

The four agents, in execution order:

1. **Requirements Analyst** — Receives the raw customer config from the intake form. Analyzes it for ambiguity, gaps, and contradictions. Runs the clarification loop with the customer through the UI. Produces a finalized, unambiguous requirements document (structured JSON) that becomes the canonical reference for all downstream agents.

2. **Solution Architect** — Receives the finalized requirements. Produces a technical design document: data models/schemas, API endpoint specifications, component breakdown, file structure, technology choices within the Aegis-supported stack, and a dependency map. This design is structured enough that the Developer agent can implement it without creative interpretation.

3. **Developer** — Receives the requirements and the technical design. Produces the actual code files: frontend components, backend routes, database schemas, and configuration files. Outputs a complete, runnable project directory. The Developer is prompt-engineered to produce clean, documented, maintainable code — not just functional code.

4. **QA Reviewer** — Receives the requirements, design, and generated code. Performs three checks: (a) functional review — does the code structure match the design, are all endpoints/components present; (b) requirements alignment — does the output address every requirement in the finalized config; (c) code quality — readability, naming conventions, basic security practices, documentation. Produces a structured review report.

**Feedback loops:** The QA Reviewer can issue two types of feedback:
- **Code revision request** → sent back to the Developer with specific issues. The Developer receives the review report and its own previous output, and produces a revised version. Hard cap: 2 revision cycles.
- **Design revision request** → sent back to the Solution Architect when the QA Reviewer identifies a structural or architectural issue that cannot be fixed by code changes alone. The Architect revises the design, and the Developer re-implements. Hard cap: 1 design revision cycle per pipeline run.

**Pipeline topology: Linear with conditional backward edges.** This is not a free-form graph. The default path is Requirements Analyst → Solution Architect → Developer → QA Reviewer → Output. The backward edges (QA → Developer, QA → Architect) are conditional and cycle-capped. This is the simplest topology that produces meaningfully better output than a single prompt, while remaining buildable in 12 weeks by a solo developer.

**Why not more agents?** Adding agents for separate frontend/backend development, database design, or testing creates coordination overhead that compounds token costs and latency. The 4-agent structure maps cleanly to the software development lifecycle (requirements → design → implementation → review) and keeps each agent's responsibility scope manageable within a single LLM context window. Agent teams (multiple agents per role) should be deferred to Stage 2.

**Why not fewer?** Collapsing Architect and Developer into one agent removes the critical separation between design and implementation — the exact discipline Aegis is designed to enforce. Removing QA eliminates the feedback mechanism that differentiates Aegis from a single-prompt approach. Three agents is the absolute minimum viable structure, but the 4-agent version is worth the marginal complexity for academic defensibility and output quality.

**Context passing strategy: Structured JSON handoffs with full upstream context.** Each agent receives: (a) the finalized customer config (always), (b) the output of the immediately preceding agent, and (c) a compressed summary of earlier stages. This avoids context window overflow while preserving traceability. Specifically:
- Solution Architect receives: full config + Requirements Analyst output
- Developer receives: full config + Architect design document (Requirements Analyst output is summarized into the design)
- QA Reviewer receives: full config + Architect design (as reference) + Developer code output

**Minimum viable differentiation from single-prompt:** The structured handoffs, the explicit design-before-implementation discipline, the QA feedback loop, and the traceable intermediate artifacts all contribute to the thesis hypothesis. Even a 4-agent linear pipeline with one feedback loop produces measurably different output characteristics than "generate a full-stack app from this description" in a single prompt.

**Tradeoffs:** More agents = more latency (each agent call takes 10-60 seconds), more tokens (each handoff includes context), more complexity to orchestrate. Fewer agents = less process fidelity, less observable intermediate work, weaker thesis argument. The 4-agent structure is the optimal balance for Stage 1.

---

### 4.2 Existing Agent Frameworks

**Recommendation: Build a custom lightweight orchestration layer. Do not use LangGraph, CrewAI, or AutoGen.**

**Research findings on current frameworks (March 2026):**

**LangGraph** is the most mature framework for stateful multi-agent workflows with cycles. It models pipelines as directed graphs with typed state schemas, supports checkpointing, and has excellent observability through LangSmith. However, it has a steep learning curve, rigid state management that becomes complex in intricate networks, and significant boilerplate. It is overkill for a 4-agent linear pipeline.

**CrewAI** has the best developer experience for role-based agent teams — you define agents with roles, backstories, and goals. It excels at linear workflows and is the fastest to prototype. However, logging and debugging are poor (a critical problem for a thesis that requires process fidelity analysis), and it struggles with cycles/feedback loops. CrewAI's abstraction also makes it harder to control exactly what prompts are sent to the LLM.

**AutoGen** (Microsoft) has shifted to maintenance mode in favor of the broader Microsoft Agent Framework. Its conversation-based approach doesn't map well to the Aegis pipeline structure. Not recommended for new projects.

**Why custom orchestration wins for Aegis:**

1. **Academic defensibility.** The orchestration layer IS the core intellectual contribution of the thesis. Using a framework means defending someone else's architectural decisions. Building custom means you own and can explain every design choice.

2. **Full prompt control.** Aegis agents need precisely crafted system prompts with structured output enforcement. Frameworks add their own system prompts, tool-calling wrappers, and abstractions that obscure what the LLM actually sees. For a thesis project where prompt engineering is a key research area, this opacity is unacceptable.

3. **Pipeline simplicity.** The Aegis pipeline is 4 agents in a line with 2 conditional backward edges. This is a state machine with ~6 states and ~8 transitions. Building this as a Python class with explicit state management takes less code than configuring LangGraph, and produces code the student fully understands.

4. **Observability by design.** Every event the pipeline emits (agent start, LLM call, output received, feedback triggered, cycle count) can be structured exactly as the observation UI needs. No framework adapter layer required.

5. **No framework lock-in risk.** Framework APIs change frequently. A custom layer built on direct Anthropic API calls has exactly one dependency — the Claude API, which has a stable interface.

**The custom orchestration layer is not complex.** It is approximately 300-500 lines of Python: a `PipelineRunner` class that manages agent sequence, state transitions, feedback routing, cycle counting, and event emission. Each agent is a Python class with a system prompt template and an `execute()` method that calls the Claude API. This is well within scope for a solo developer in 12 weeks.

**Tradeoff acknowledged:** No free checkpointing, no built-in retry logic, no LangSmith-style debugging UI. These must be built manually, but for a 4-agent pipeline, the effort is minimal compared to learning and adapting a framework.

---

### 4.3 Failure Modes of Multi-Agent Pipelines

**Research findings from NeurIPS 2025 MAST taxonomy and related work:**

A major empirical study (Cemri et al., NeurIPS 2025) analyzed 1,642 multi-agent system execution traces and found failure rates between 41% and 87% across 7 state-of-the-art open-source MAS. The study found that many failures arise from organizational design and agent coordination problems rather than individual agent limitations. The key failure categories relevant to Aegis:

**1. Hallucination propagation (HIGH risk for Aegis).** When the Requirements Analyst misinterprets a customer input and produces a flawed requirement, every downstream agent builds on that flaw. The Solution Architect designs for the wrong requirement, the Developer implements the wrong design, and the QA Reviewer may not catch it if the code matches the (flawed) design. This is the most dangerous failure mode because it produces coherent but wrong output.

*Mitigation:* The clarification loop is the primary defense. The Requirements Analyst must surface uncertainty rather than guessing. The finalized config includes explicit traceability — every requirement is linked to a specific customer input field. The QA Reviewer checks code against the original customer config, not just the Architect's design, providing a second line of defense.

**2. Role drift (MEDIUM risk).** An agent starts performing tasks outside its defined responsibility. The Developer starts making architectural decisions the Architect should have made. The QA Reviewer starts rewriting code instead of reviewing it.

*Mitigation:* Strict system prompts with explicit role boundaries and output format enforcement. Each agent's system prompt includes a "you must NOT" section. Structured output schemas constrain what each agent can produce — the Developer cannot modify the design document, only produce code files.

**3. Infinite loops (LOW risk given hard caps, but must be handled).** The QA Reviewer rejects code, the Developer revises, QA rejects again, indefinitely.

*Mitigation:* Hard cycle caps (2 for code revision, 1 for design revision) are the primary defense. Additionally, the QA Reviewer's revision request must include specific, actionable issues — not vague "needs improvement." If the cap is reached, the pipeline outputs the best available version with a quality flag indicating that review issues remain unresolved.

**4. Context window overflow (MEDIUM risk).** As agents pass context forward, the accumulated text may exceed the model's effective context window, degrading output quality even if technically within token limits.

*Mitigation:* Structured handoffs with compression. The Developer does not receive the raw Requirements Analyst output — it receives the Architect's design, which is a compressed, structured representation of the requirements. Full context is only maintained for the immediately preceding agent's output.

**5. Cascading format errors (MEDIUM risk).** If one agent produces output that doesn't match the expected schema, the next agent receives malformed input and may produce garbage or hallucinate a recovery.

*Mitigation:* Pydantic validation on every agent output before passing to the next agent. If validation fails, the agent is re-prompted once with the validation error. If it fails again, the pipeline halts with a clear error message to the user.

**Graceful degradation strategy:** When an agent fails after retries, the pipeline does not silently continue. It emits a pipeline-halted event to the UI explaining what happened in business language (e.g., "Our design team encountered an issue they couldn't resolve. Our team lead is reviewing the situation."). The user is given the option to restart the pipeline or accept partial output.

---

### 4.4 Customer Intake Form — Structure & Clarification Loop

**Form input categories (7 sections):**

**Section 1: Business Context (all required)**
- Business name (free text)
- Industry/sector (dropdown: retail, food & beverage, professional services, healthcare, education, manufacturing, other + specify)
- Brief business description (free text, 2-3 sentences, with placeholder example)
- Number of employees (dropdown: 1-5, 6-20, 21-50, 50+)

**Section 2: Problem Statement (required)**
- What problem are you trying to solve? (free text, guided with examples: "I need to track customer orders", "I want customers to book appointments online", "I need to manage my inventory")
- Who will use this software? (multi-select: you/owner, employees, customers, all of these)
- How is this currently handled? (free text, optional, with hint: "spreadsheet, paper, phone calls, nothing yet")

**Section 3: Core Features (required)**
- What should users be able to do? (free text, with guided prompt: "List the main actions, e.g., 'add new customers', 'view order history', 'generate monthly reports'")
- Priority ranking of listed features (drag-and-drop ranking after entry, or numbered)

**Section 4: Data & Content (required where applicable)**
- What information do you need to store? (free text, with examples: "customer names and phone numbers", "product names, prices, and stock levels")
- Do you have existing data to import? (yes/no; if yes, file upload with category tag: "existing data", "reference spreadsheet", "sample document")
- Estimated data volume (dropdown: under 100 records, 100-1000, 1000-10000, 10000+)

**Section 5: Design Preferences (optional)**
- Do you have brand colors? (color picker or hex input, optional)
- Do you have a logo? (file upload, category: "branding material")
- Any design references or screenshots of tools you like? (file upload, category: "design reference")
- Preferred style (dropdown: clean & minimal, professional & corporate, modern & colorful, no preference)

**Section 6: Technical Requirements (required, constrained)**
- Who needs to access this? (dropdown: just me, my team on the same network, anyone on the internet)
- Do users need to log in? (yes/no)
- Do you need the app to work on mobile phones? (yes/no/nice to have)

**Section 7: Timeline & Constraints (optional)**
- Any hard deadline? (date picker, optional)
- Anything else we should know? (free text, optional)

**Output schema — the raw config file is a JSON object with these top-level keys:**
```json
{
  "business_context": { "name": "", "industry": "", "description": "", "size": "" },
  "problem_statement": { "problem": "", "users": [], "current_process": "" },
  "features": { "requested": [{ "description": "", "priority": 1 }] },
  "data": { "entities": "", "has_existing_data": false, "uploads": [], "volume": "" },
  "design": { "colors": null, "logo": null, "references": [], "style": "" },
  "technical": { "access_scope": "", "auth_required": false, "mobile": "" },
  "meta": { "deadline": null, "notes": "", "submitted_at": "" }
}
```

**Mandatory minimum config:** Sections 1, 2, and 3 must be filled. Section 4's data entities field is required. Sections 5, 6, and 7 have sensible defaults (no brand, anyone-on-internet access, login required, mobile nice-to-have, no deadline).

**Field dependencies:**
- "Do you have existing data?" = yes → shows file upload
- "Who needs to access this?" = "anyone on the internet" → shows advisory about hosting requirements
- "Do users need to log in?" = yes → adds a sub-question: "What user roles do you need?" (free text with examples)

---

**First Agent Clarification Loop Design:**

**How the Requirements Analyst analyzes the config:** The agent receives the raw config JSON and its system prompt instructs it to check for: (a) vague feature descriptions that could be interpreted multiple ways, (b) contradictions (e.g., "no login required" but "different user roles"), (c) missing information that would block design (e.g., features mention "reports" but no data entities describe what would be reported on), (d) scope risks (features that are too complex for automated generation).

**Question surfacing:** Questions are grouped by topic and presented to the customer in the UI as a structured questionnaire — not a chatbot conversation. Each question includes: the original customer input being clarified, what specifically is ambiguous, and 2-3 suggested answers where applicable. Maximum 10 questions per clarification round.

**Answer incorporation:** The agent receives the customer's answers and updates the config directly. Answers are interpreted by the agent, not inserted verbatim — the agent translates business language into structured config updates.

**Exit condition (3-part termination strategy):**
1. **Completeness check:** The agent evaluates whether every required field in the config is specific enough to produce a technical design. If yes → exit loop.
2. **Hard round cap:** Maximum 3 clarification rounds. If after 3 rounds the config still has ambiguity, the agent makes reasonable assumptions, documents them explicitly in the config as `"assumed": true` fields, and proceeds.
3. **Customer opt-out:** The customer can choose "proceed with current information" at any round, which triggers the assumption behavior from point 2.

**Finalized config presentation:** Before the pipeline starts, the customer sees a human-readable summary of the finalized config — not the JSON, but a structured "project brief" generated by the Requirements Analyst. The summary includes any assumptions made. The customer confirms with a single "Start Building" action.

**Logging:** Every clarification exchange (questions asked, answers received, config changes made) is logged as a structured event and displayed in the observation UI's activity feed as a visible "team discussion" between the customer and the requirements analyst.

---

### 4.5 Observation UI — Design for Non-Technical Users

**Core design principle: The UI tells a story of a team building software, not a log of API calls.**

**Agent activity translation:** Each pipeline event is mapped to a business-language message with a defined abstraction level:

| Internal Event | User-Facing Message | Detail Level |
|---|---|---|
| `requirements_analyst.start` | "Your project analyst is reviewing your requirements..." | Summary only |
| `requirements_analyst.clarification_needed` | "Your analyst has a few questions to make sure we build exactly what you need." | Interactive — shows questions |
| `requirements_analyst.config_finalized` | "Requirements confirmed! Here's your project brief." | Shows readable summary |
| `architect.start` | "Our architect is designing the structure of your application..." | Summary only |
| `architect.complete` | "Application design complete. Here's what we're building:" | Shows simplified design overview (component names, not code) |
| `developer.start` | "Our developer is building your application..." | Summary + progress indicators |
| `developer.file_generated` | "Built: User Dashboard page" | Per-file progress, human-readable names |
| `qa_reviewer.start` | "Quality review in progress..." | Summary only |
| `qa_reviewer.revision_requested` | "Our reviewer found some improvements. Sending back to the developer." | Shows summary of issues in business language |
| `qa_reviewer.approved` | "Your application passed quality review!" | Summary |
| `pipeline.complete` | "Your application is ready! Here's what we built." | Shows final deliverable summary |
| `pipeline.error` | "We ran into an issue. Our team lead is looking into it." | Simplified error, no stack traces |

**Pipeline progress representation:** A horizontal step indicator showing 4 stages: Requirements → Design → Development → Review. The current active stage is highlighted. Completed stages show a checkmark. This gives the customer an instant understanding of where their project is.

**Code output presentation:** The non-technical user sees a "Project Summary" view, not raw code. This includes: application name, list of pages/screens built, list of features implemented (mapped back to their original feature requests), and a "files delivered" count. A collapsible "Technical Details" section is available for technical users or the thesis evaluator, showing the actual file tree and code.

**Clarification loop UI:** When the Requirements Analyst needs clarification, the step indicator pauses on "Requirements" and the main content area transitions to a form-like questionnaire. Each question shows the relevant context from the customer's original input. The customer answers and submits. The activity feed shows this as a natural back-and-forth conversation.

**Error communication:** Errors are presented as team status updates, never as technical error messages. "Our developer is having trouble with one of the features and is trying a different approach" (retry), "We weren't able to complete the payment processing feature — here's what we were able to build" (partial output with explanation).

**Stage transitions:** When moving between pipeline phases, the UI shows a brief transition message ("Your analyst has handed off to our architect") and the step indicator advances. This makes the handoff visible and reinforces the multi-agent team metaphor.

---

### 5.1 Technology Stack

**LLM API: Anthropic Claude API**
- **Primary model: Claude Sonnet 4.5** (`claude-sonnet-4-5-20250514`) — $3/M input, $15/M output. Best balance of capability and cost. Strong at code generation, structured output, and instruction following. 200K default context window is more than sufficient for agent handoffs.
- **Lightweight tasks: Claude Haiku 4.5** (`claude-haiku-4-5-20251001`) — $1/M input, $5/M output. Used for output validation, format checking, and the LLM-as-judge evaluation. 
- **Prompt caching: Enabled.** System prompts are identical across pipeline runs. Caching reduces input costs by up to 90% for the static system prompt portion after the first call.

**Budget analysis at $50-150/month:** A single pipeline run with 4 agents using Sonnet 4.5, assuming ~4K input tokens and ~4K output tokens per agent call (conservative for code generation), plus 2 QA revision cycles, costs approximately $0.50-1.00 per run. At $100/month budget, this allows 100-200 pipeline runs — far more than needed for development, testing, and beta evaluation.

**Backend: Python 3.12 + FastAPI**
- FastAPI provides async request handling, automatic OpenAPI documentation, Pydantic model integration for request/response validation, and native SSE support via `sse-starlette`.
- Python is the best-supported language for LLM API clients (Anthropic's official SDK is Python-first).
- Pydantic v2 is used for all inter-agent message schemas, providing runtime validation and serialization.
- The student's basic Python knowledge is sufficient because AI-assisted development works extremely well with Python/FastAPI — it is the most common stack in LLM application tutorials and Claude's training data.

**Real-time communication: Server-Sent Events (SSE)**
- SSE is one-directional (server → client), which is exactly what the observation UI needs — the backend pushes events, the frontend listens and renders.
- The only bidirectional interaction is the clarification loop, which uses standard REST endpoints (customer submits answers via POST, receives next questions via the SSE stream).
- SSE is simpler to implement than WebSocket, works through proxies and load balancers without special configuration, and auto-reconnects on connection drop.
- Implementation: `sse-starlette` library on the backend, native `EventSource` API on the frontend.

**Frontend: Next.js 14+ (App Router) with React and Tailwind CSS**
- Next.js provides file-based routing, server-side rendering for the initial page load, and excellent developer experience with AI-assisted coding.
- Tailwind CSS enables rapid UI development without writing custom CSS — critical for a student relying on AI assistance for frontend work.
- shadcn/ui component library for consistent, professional UI components (forms, cards, progress indicators, collapsible sections).
- The frontend is deliberately thin — it renders events from the SSE stream and hosts the intake form. No complex client-side state management is needed. React's built-in `useState` and `useReducer` are sufficient.

**Database/State: SQLite + filesystem**
- SQLite stores: pipeline run state, execution logs (every event with timestamp), customer configs, agent outputs (metadata — the actual outputs are files).
- The filesystem stores: generated code output (as actual files in a project directory), uploaded customer files, agent output artifacts.
- No need for PostgreSQL or any server database for a single-customer system. SQLite is zero-configuration, embedded, and sufficient.
- If the student later needs to query logs for evaluation analysis, SQLite supports full SQL.

**Deployment platform: Railway (backend) + Vercel (frontend)**
- **Railway** ($5/month Hobby plan): Deploys the Python/FastAPI backend directly from GitHub. Provides a managed PostgreSQL addon if SQLite proves insufficient (unlikely). Usage-based billing keeps costs minimal. HTTPS included.
- **Vercel** (free tier): Deploys the Next.js frontend. Free tier includes HTTPS, custom domains, and is purpose-built for Next.js. Zero configuration needed.
- **Total deployment cost: ~$5-10/month** — well within budget alongside LLM API costs.
- Both platforms deploy on `git push`, which means the student can deploy continuously without DevOps overhead.

**Access control for beta:** Vercel supports password protection on preview deployments (Vercel Authentication). For the Railway backend, a simple API key middleware (a shared secret in an environment variable, sent as a header by the frontend) is sufficient to prevent unauthorized access.

**Evaluation tooling:**
- Pipeline execution logs in SQLite, queryable with standard SQL for process fidelity analysis.
- A simple Python script that runs benchmark tasks through both Aegis and a single-prompt baseline, recording outputs and metrics.
- LLM-as-judge implemented as a standalone Python script using Haiku 4.5 to score outputs on a rubric.
- Beta user feedback collected via a structured form built into the Aegis frontend (shown after pipeline completion).

---

### 5.2 Prompt Engineering Strategy

**Role-specialized agent prompts follow this structure:**

```
[IDENTITY] You are the {Role Name} at Aegis, a virtual software company.
[RESPONSIBILITY] Your job is to {specific task}. You receive {input description} and produce {output description}.
[CONSTRAINTS] You must NOT {explicit boundary list}. You must ALWAYS {mandatory behaviors}.
[OUTPUT FORMAT] Your response must be valid JSON matching this exact schema: {schema}
[CONTEXT] Here is the customer's project: {config}. Here is the previous agent's output: {upstream output}.
[TASK] Analyze the above and produce your output now.
```

**Key prompting patterns:**

1. **Persona prompting with explicit boundaries.** Each agent has a professional identity ("You are a senior requirements analyst") AND explicit prohibitions ("You must NOT make design decisions — that is the architect's job"). This prevents role drift.

2. **Structured output enforcement.** Every agent must return valid JSON matching a Pydantic schema. The system prompt includes the exact JSON schema and a brief example. Output is validated with Pydantic before being passed downstream. If validation fails, the agent is re-prompted once with the error message.

3. **Chain-of-thought with structured output.** Agents are instructed to include a `"reasoning"` field in their JSON output where they explain their decisions before giving the actual output. This serves dual purposes: it improves output quality (CoT effect) and provides observable intermediate reasoning for the UI and evaluation logs.

4. **Context passing: structured schema, not full dump.** Each agent receives only what it needs in a structured format. The Developer receives the Architect's design document (which already distills the requirements), not the raw conversation history of the clarification loop. This keeps context focused and avoids the "lost in the middle" problem with long contexts.

**Preventing role drift:** Beyond explicit prohibitions in system prompts, the output schema itself constrains behavior. The Developer agent's output schema has fields for code files only — it literally cannot produce a design document because the schema doesn't allow it. The Architect's schema has fields for component specifications, not code. Schema-as-constraint is more reliable than prompt-as-constraint.

**Consistent output formats:** All inter-agent messages use Pydantic models defined in a shared `schemas.py` file. This means the format is validated programmatically, not just requested in the prompt. The prompt tells the agent what format to use; Pydantic enforces it.

---

### 5.3 Evaluation Infrastructure

**Benchmark task set: 5 tasks across 3 complexity tiers.**

- **Tier 1 — Simple (2 tasks):** A personal to-do list app with categories. A simple contact directory with search.
- **Tier 2 — Medium (2 tasks):** An appointment booking system for a small clinic. An inventory management tool for a retail shop.
- **Tier 3 — Complex (1 task):** A customer order tracking system with status updates and reporting for a small e-commerce business.

Each task has: a pre-filled customer config (simulating what a real customer would submit), a set of 5-10 unit tests that define functional correctness, and a requirements checklist for alignment scoring.

5 tasks is sufficient for a thesis evaluation. More tasks add diminishing returns given the time cost of running each through both Aegis and the baseline.

**LLM-as-judge implementation:** A standalone Python script that sends each Aegis output (and baseline output) to Haiku 4.5 with a scoring rubric. The rubric scores on: requirements coverage (1-5), code organization (1-5), documentation quality (1-5), and overall coherence (1-5). The judge receives the original customer config and the generated code, and scores independently. Each evaluation is run 3 times and averaged to reduce variance. Estimated cost: ~$2-5 per full evaluation run.

**Pipeline execution log structure:**
```json
{
  "run_id": "uuid",
  "timestamp": "ISO-8601",
  "task_id": "benchmark_task_1",
  "events": [
    {
      "event_id": "uuid",
      "timestamp": "ISO-8601",
      "agent": "requirements_analyst",
      "event_type": "agent_start | llm_call | output_produced | validation_passed | feedback_sent | error",
      "data": { },
      "tokens_used": { "input": 0, "output": 0 },
      "duration_ms": 0
    }
  ],
  "total_tokens": { "input": 0, "output": 0 },
  "total_duration_ms": 0,
  "total_cost_usd": 0.0,
  "outcome": "success | partial | failed",
  "feedback_cycles": { "code_revisions": 0, "design_revisions": 0 }
}
```

This structure directly supports process fidelity analysis: you can verify agent sequence, count feedback cycles, measure per-agent latency and token usage, and identify where failures occur.

**Beta user feedback form (shown after pipeline completion):**

Since the beta users are you and your supervisor, the form should capture structured academic data:

1. "How well does the output match the project description you provided?" (1-5 scale)
2. "How would you rate the quality of the generated application?" (1-5 scale)
3. "Was the process of watching the agents work understandable?" (1-5 scale)
4. "Was the clarification process helpful?" (1-5 scale)
5. "Were there any moments where you lost trust in the system?" (yes/no + free text)
6. "What would you improve?" (free text)
7. "Would you use this system again for a similar task?" (yes/no)

---

### 5.4 Security — Minimum Requirements

1. **API key management:** All secrets (Anthropic API key, Railway API tokens) stored as environment variables. Never committed to git. Use a `.env` file locally (gitignored) and platform environment variable settings in deployment.
2. **Beta access control:** Frontend deployed on Vercel with Vercel Authentication (password protection). Backend API requires an `X-API-Key` header matching an environment variable — the frontend includes this automatically.
3. **HTTPS:** Both Vercel and Railway provide HTTPS by default. No additional configuration needed.
4. **Input sanitization:** Customer form inputs are validated and sanitized before being included in LLM prompts to prevent prompt injection. The config JSON is schema-validated with Pydantic.

---

## PART 2 — Finalized Technical Decisions

| Decision | Choice | 
|---|---|
| **Agent count** | 4 (Requirements Analyst, Solution Architect, Developer, QA Reviewer) |
| **Pipeline topology** | Linear with conditional backward edges (QA→Dev: max 2 cycles, QA→Architect: max 1 cycle) |
| **Orchestration** | Custom Python orchestration layer (~300-500 LOC), no framework |
| **LLM provider** | Anthropic Claude API |
| **Primary model** | Claude Sonnet 4.5 ($3/$15 per M tokens) |
| **Secondary model** | Claude Haiku 4.5 ($1/$5 per M tokens) for validation and evaluation |
| **Backend** | Python 3.12 + FastAPI |
| **Frontend** | Next.js 14+ (App Router) + Tailwind CSS + shadcn/ui |
| **Real-time** | Server-Sent Events (SSE) via sse-starlette |
| **Database** | SQLite (pipeline state + logs) + filesystem (code artifacts) |
| **Inter-agent format** | JSON with Pydantic v2 schema validation |
| **Deployment — backend** | Railway ($5/month Hobby plan) |
| **Deployment — frontend** | Vercel (free tier) |
| **Access control** | Vercel Authentication + API key header |
| **Evaluation model** | Haiku 4.5 as LLM-as-judge |
| **Benchmark tasks** | 5 tasks across 3 complexity tiers |

---

## PART 3 — Detailed Implementation Plan

### Student Profile Assumptions
- 20-30 hours/week available
- Starting from zero code
- AI-assisted development throughout
- Basic Python; minimal frontend experience
- $50-150/month LLM budget
- Midterm (Week 8): written report + working prototype demo
- Beta users: student + supervisor

---

### PHASE 0: Project Setup (Week 4 — Days 1-3)

**What to build:** Repository structure, development environment, and basic project skeleton.

**Tasks:**
1. Create a GitHub repository with this structure:
```
aegis/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app entry
│   │   ├── config.py            # Settings & env vars
│   │   ├── schemas/             # Pydantic models for all inter-agent messages
│   │   ├── agents/              # Agent classes
│   │   ├── pipeline/            # Orchestration engine
│   │   ├── api/                 # REST & SSE endpoints
│   │   └── db/                  # SQLite models & queries
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── app/                 # Next.js App Router pages
│   │   ├── components/          # React components
│   │   └── lib/                 # Utilities, SSE client, API client
│   ├── package.json
│   └── tailwind.config.js
├── evaluation/
│   ├── benchmarks/              # Benchmark task configs
│   ├── scripts/                 # Evaluation runner scripts
│   └── results/                 # Evaluation output
├── docs/
│   └── architecture.md
├── .gitignore
└── README.md
```

2. Set up Python virtual environment, install FastAPI, uvicorn, sse-starlette, anthropic SDK, pydantic, sqlite3.
3. Set up Next.js project with Tailwind CSS and shadcn/ui.
4. Create `.env` file with `ANTHROPIC_API_KEY` placeholder.
5. Verify Claude API access works with a simple test call.

**Definition of done:** Repo exists, both backend and frontend start without errors, a test API call to Claude returns a response.

**Time estimate:** 4-6 hours.

---

### PHASE 1: Core Pipeline Engine (Week 4-5 — ~10 days)

**What to build:** The orchestration engine, agent base class, inter-agent schemas, and a single working agent (Requirements Analyst) that can process a config and produce output.

**Tasks:**

**Week 4 (remaining days after Phase 0):**

1. **Define all Pydantic schemas** (`backend/app/schemas/`):
   - `CustomerConfig` — the raw config from the intake form
   - `FinalizedRequirements` — output of Requirements Analyst
   - `TechnicalDesign` — output of Solution Architect
   - `CodeOutput` — output of Developer (file manifest + code content)
   - `QAReview` — output of QA Reviewer (issues list + verdict)
   - `PipelineEvent` — the SSE event format for the frontend
   - `AgentMessage` — the inter-agent handoff wrapper

2. **Build the Agent base class** (`backend/app/agents/base.py`):
   - `__init__`: takes system prompt template, model name, output schema
   - `execute(context: dict) -> AgentOutput`: calls Claude API, validates output against schema, retries once on validation failure
   - Emits `PipelineEvent` objects for every action (start, llm_call, output, error)

3. **Build the PipelineRunner** (`backend/app/pipeline/runner.py`):
   - State machine with states: `INTAKE`, `REQUIREMENTS`, `DESIGN`, `DEVELOPMENT`, `REVIEW`, `REVISION`, `COMPLETE`, `FAILED`
   - Manages agent sequence, passes context between agents
   - Handles feedback routing (QA → Dev or QA → Architect)
   - Enforces cycle caps
   - Emits events via a callback function (to be connected to SSE later)

4. **Implement the Requirements Analyst agent** (`backend/app/agents/requirements_analyst.py`):
   - System prompt: analyzes raw config, identifies ambiguities, produces clarification questions OR finalized requirements
   - Two modes: `analyze` (produces questions) and `finalize` (produces finalized config after answers received)

**Week 5:**

5. **Implement the Solution Architect agent** (`backend/app/agents/architect.py`):
   - Receives finalized requirements, produces technical design
   - Design includes: data models (table/collection schemas), API endpoints, frontend components, file structure

6. **Implement the Developer agent** (`backend/app/agents/developer.py`):
   - Receives requirements + design, produces code files
   - Output is a structured list of files with path and content
   - System prompt enforces code quality standards: clear naming, comments, consistent style

7. **Implement the QA Reviewer agent** (`backend/app/agents/qa_reviewer.py`):
   - Receives requirements + design + code
   - Produces review report: list of issues (each with severity, description, affected file) + overall verdict (approve/revise-code/revise-design)

8. **Integration test:** Run the full pipeline from a hardcoded test config through all 4 agents, verify output, check event sequence.

**Definition of done:** A Python script can trigger a full pipeline run from a JSON config file, all 4 agents execute in sequence, feedback loops work when QA requests revision, events are emitted in order, and the final output includes generated code files.

**Potential blockers:**
- Claude API output not matching Pydantic schemas → solution: iterate on system prompts, add output examples to prompts
- Agent taking too long → solution: set API timeout to 120 seconds, use Sonnet not Opus
- Output validation failures → solution: re-prompt with error, add fallback for malformed output

**Time estimate:** 30-40 hours total across Week 4-5.

---

### PHASE 2: API Layer & SSE Streaming (Week 5-6 — ~7 days)

**What to build:** REST API endpoints, SSE event streaming, and the connection between the pipeline engine and the HTTP layer.

**Tasks:**

1. **REST endpoints** (`backend/app/api/`):
   - `POST /api/pipeline/start` — receives customer config JSON, starts pipeline, returns run_id
   - `GET /api/pipeline/{run_id}/events` — SSE endpoint, streams pipeline events in real-time
   - `POST /api/pipeline/{run_id}/clarification` — receives customer answers to clarification questions
   - `GET /api/pipeline/{run_id}/status` — returns current pipeline state
   - `GET /api/pipeline/{run_id}/output` — returns final output (code files) when complete

2. **SSE integration:** Connect PipelineRunner's event callback to the SSE endpoint. Each `PipelineEvent` is serialized to JSON and pushed to the SSE stream.

3. **Background execution:** Pipeline runs in a background task (FastAPI's `BackgroundTasks` or `asyncio.create_task`). The SSE endpoint reads events from a queue that the pipeline writes to.

4. **SQLite logging:** Every event is persisted to SQLite as it's emitted, creating the execution log required for evaluation.

5. **Basic error handling:** API returns proper HTTP status codes, pipeline errors are caught and emitted as error events.

**Definition of done:** You can start a pipeline via curl/Postman, connect to the SSE stream, and see events appear in real time as agents execute. Clarification questions are surfaced via SSE, answers are submitted via POST, and the pipeline resumes.

**Time estimate:** 15-20 hours.

---

### PHASE 3: Frontend — Observation UI (Week 6-7 — ~10 days)

**What to build:** The complete frontend: intake form, observation dashboard, and output viewer.

**Tasks:**

**Week 6:**

1. **Intake form page** (`/`):
   - Multi-step form matching the 7 sections defined in Section 4.4
   - Field validation (required fields, format checks)
   - File upload support for design references and existing data
   - Form submission sends config to `POST /api/pipeline/start`

2. **Observation dashboard** (`/project/{run_id}`):
   - Step indicator (4 stages: Requirements → Design → Development → Review)
   - Activity feed showing pipeline events as they arrive via SSE
   - Event messages translated to business language (mapping table from Section 4.5)

**Week 7:**

3. **Clarification UI:**
   - When clarification events arrive, display the questionnaire in the main content area
   - Customer answers submitted via POST, pipeline resumes automatically

4. **Output viewer** (`/project/{run_id}/output`):
   - Project summary (features built, pages created)
   - Collapsible file tree with code preview
   - Download button for the generated project

5. **Polish:**
   - Loading states, error states, empty states
   - Responsive layout (works on desktop and tablet)
   - Professional styling with shadcn/ui components

**Definition of done:** A user can open the app in a browser, fill out the intake form, watch agents work in real-time with business-language updates, answer clarification questions, and view/download the final output.

**Time estimate:** 25-35 hours.

---

### ⚡ MIDTERM DELIVERABLE (Week 8)

**What to demonstrate:**
1. **Live demo:** Walk through the full pipeline from intake form to generated code output, showing the observation UI in real-time. Use one of the Tier 1 benchmark tasks (to-do list app) as the demo scenario.
2. **The demo must show:** (a) customer filling out the intake form, (b) Requirements Analyst analyzing and (optionally) asking clarification questions, (c) Architect producing a design, (d) Developer generating code, (e) QA reviewing and (if triggered) requesting revision, (f) final output visible in the UI.

**What to write in the midterm report:**
1. Project motivation and problem statement
2. Literature review: existing AI coding tools and their limitations, multi-agent systems research
3. Architecture overview: 4-agent pipeline, topology, technology stack choices with justification
4. Current implementation status with screenshots
5. Evaluation methodology (planned): the 4-dimension framework, benchmark tasks, comparative baseline
6. Timeline for remaining 8 weeks

**What is acceptable to be incomplete at Week 8:**
- The generated code doesn't need to be production-quality — functional output that demonstrates the pipeline works is sufficient
- File upload in the intake form can be stubbed
- The output viewer can be basic (file list + raw code display)
- Only 1-2 benchmark tasks need to work reliably

**What must work at Week 8:**
- Full pipeline execution from form to output, end-to-end
- SSE streaming with real-time event display
- At least one successful clarification loop demo
- The observation UI must be presentable (not a terminal)

---

### PHASE 4: Quality & Reliability (Week 9-10 — ~10 days)

**What to build:** Prompt refinement, error handling hardening, and output quality improvement.

**Tasks:**

1. **Prompt iteration:** Run all 5 benchmark tasks through the pipeline. Analyze outputs. Refine system prompts to improve:
   - Code quality (naming, structure, documentation)
   - Requirements coverage (no missed features)
   - Design completeness (no missing data models or endpoints)

2. **Error handling hardening:**
   - Graceful handling of Claude API rate limits (exponential backoff)
   - Graceful handling of API timeouts
   - Pipeline recovery: if an agent fails mid-run, save state and allow manual retry
   - User-facing error messages for all failure modes

3. **Output format refinement:**
   - Ensure generated code files are actually runnable (correct imports, valid syntax)
   - Add a syntax validation step after the Developer agent (quick automated check, not an LLM call)

4. **Prompt caching implementation:**
   - Enable Anthropic prompt caching for system prompts
   - Measure cost savings

**Definition of done:** All 5 benchmark tasks produce reasonable output. Error handling works for common failure modes. Pipeline is reliable enough for repeated demonstration.

**Time estimate:** 20-25 hours.

---

### PHASE 5: Evaluation Framework (Week 11-12 — ~10 days)

**What to build:** The complete evaluation infrastructure and run the evaluation.

**Tasks:**

1. **Baseline implementation:** Create a script that sends each benchmark task to Claude Sonnet 4.5 as a single prompt ("Build me a [description from config]") and saves the output. This is the comparative baseline.

2. **LLM-as-judge script:** Implement the Haiku 4.5-based evaluation scoring. Each output (Aegis and baseline) is scored on the 4-dimension rubric. Each scoring is run 3 times and averaged.

3. **Functional correctness testing:** Write the predefined unit tests for each benchmark task. Run them against both Aegis and baseline outputs. Record pass rates.

4. **Process fidelity analysis:** Query the SQLite execution logs. Verify: correct agent sequence, feedback loops triggered when appropriate, cycle caps respected, all events properly logged.

5. **Run the full evaluation:** Execute all 5 benchmark tasks through both Aegis and baseline. Collect all metrics. Compile into a results table.

6. **Beta evaluation:** You and your supervisor each run 2-3 scenarios through the deployed system. Fill out the feedback forms. Record observations.

**Definition of done:** Complete evaluation data for all 4 dimensions across all 5 benchmark tasks, for both Aegis and baseline.

**Time estimate:** 20-30 hours.

---

### PHASE 6: Deployment & Beta (Week 12-14 — ~10 days)

**What to build:** Production deployment and beta-ready system.

**Tasks:**

1. **Backend deployment on Railway:**
   - Connect GitHub repo to Railway
   - Set environment variables (ANTHROPIC_API_KEY, API_KEY for access control)
   - Verify SSE streaming works through Railway's proxy
   - Test with a benchmark task end-to-end

2. **Frontend deployment on Vercel:**
   - Connect GitHub repo to Vercel
   - Set environment variables (backend URL, API key)
   - Enable Vercel Authentication for access control
   - Test end-to-end from Vercel frontend to Railway backend

3. **Beta testing:**
   - Run 3-5 scenarios through the deployed system
   - Supervisor runs 1-2 scenarios independently
   - Collect feedback via the built-in feedback form
   - Fix any deployment-specific issues

**Definition of done:** System is live on the internet, accessible via a URL, protected by access control, and has been used by both the student and supervisor.

**Time estimate:** 15-20 hours.

---

### PHASE 7: Thesis Writing & Final Presentation (Week 13-16 — ongoing alongside Phase 6)

**What to produce:** Complete thesis document and final presentation.

**Thesis structure:**
1. Introduction & motivation
2. Literature review (multi-agent systems, AI coding tools, software engineering process models)
3. System architecture (full technical description of Aegis)
4. Implementation details (technology choices with justification, prompt engineering approach, pipeline design)
5. Evaluation methodology
6. Results & analysis (with comparison tables and figures)
7. Discussion (limitations, what worked, what didn't, lessons learned)
8. Conclusion & future work (Stage 2 possibilities)

**Final presentation:** Live demo of the deployed system + evaluation results slides. The demo should be rehearsed and use a prepared scenario that reliably completes in under 5 minutes.

**Time estimate:** 30-40 hours across Weeks 13-16 (parallel with Phase 6).

---

### Week-by-Week Summary

| Week | Phase | Key Deliverable |
|------|-------|----------------|
| 4 | 0 + 1 start | Repo setup, schemas defined, agent base class, Requirements Analyst working |
| 5 | 1 complete + 2 start | All 4 agents working, pipeline runs end-to-end, API endpoints started |
| 6 | 2 complete + 3 start | SSE streaming works, intake form built, observation UI started |
| 7 | 3 complete | Full frontend working, end-to-end demo possible |
| **8** | **MIDTERM** | **Live demo + written midterm report** |
| 9 | 4 start | Prompt refinement, run all benchmarks |
| 10 | 4 complete | Error handling hardened, output quality improved |
| 11 | 5 start | Baseline implemented, evaluation scripts ready |
| 12 | 5 complete + 6 start | Full evaluation run complete, deployment started |
| 13 | 6 complete + 7 start | System deployed, beta testing, thesis writing begins |
| 14 | 7 | Beta complete, thesis first draft |
| 15 | 7 | Thesis revision, presentation preparation |
| **16** | **FINAL** | **Final presentation + thesis submission** |

---

## PART 4 — Open Items for Supervisor Input

1. **Midterm report format and length requirements.** The plan assumes a report of 15-20 pages. Confirm with supervisor if there is a specific template or format required by the department.

2. **Thesis format and structure.** Confirm if the department has a LaTeX or Word template, required sections, citation style (IEEE, APA, etc.), and minimum/maximum page count.

3. **LLM API budget confirmation.** The plan is designed for $50-150/month. If the department or supervisor can provide any API credits or funding, this would allow more aggressive testing and the use of Opus-tier models for the Architect agent.

4. **Evaluation criteria weighting.** The 4-dimension evaluation framework is committed, but the relative weighting of each dimension for the final thesis assessment should be discussed with the supervisor.

5. **Beta evaluation protocol.** Confirm with supervisor: how many scenarios should the supervisor evaluate independently? Should the supervisor evaluate blind (without knowing which output is Aegis vs baseline)?

6. **Code submission format.** Does the department require the source code to be submitted alongside the thesis? If so, in what format (GitHub link, USB drive, ZIP archive)?

7. **Presentation format and duration.** Confirm the expected duration and format of both the midterm and final presentations (slides + live demo, or slides only?).

---

*End of document. This document should be reviewed, discussed with the supervisor where indicated, and committed to as the project's guiding plan.*
