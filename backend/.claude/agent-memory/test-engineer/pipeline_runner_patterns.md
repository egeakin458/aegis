---
name: pipeline_runner_patterns
description: PipelineRunner state machine behavior, cycle caps, context keys, and how to mock agents without real LLM calls
type: project
---

## PipelineRunner key behaviors

**Settings** (from app/config.py):
- max_code_revision_cycles = 2
- max_design_revision_cycles = 1
- max_clarification_rounds = 3

**State machine transitions:**
INTAKE → REQUIREMENTS → DESIGN → DEVELOPMENT → REVIEW → COMPLETE
- revise_code → CODE_REVISION → DEVELOPMENT → REVIEW (max 2 cycles)
- revise_design → DESIGN_REVISION → DEVELOPMENT → REVIEW (max 1 cycle)
- needs_clarification → CLARIFICATION (pipeline pauses, resume() continues)

**Context keys each agent receives:**
- RA: customer_config, mode ("analyze" | "finalize"), clarification_history
- SA: finalized_config only (exactly these keys, no extras)
- Dev: finalized_config, technical_design (first run); + previous_code, qa_review (revision)
- QA: finalized_config, technical_design, code_output
- SA on design revision: finalized_config, previous_design, qa_review

**Clarification cap logic:**
at_round_cap = len(clarification_history) >= max_clarification_rounds
mode = "finalize" if at_round_cap else "analyze"
If RA returns needs_clarification=True AND not at_round_cap → state=CLARIFICATION
Otherwise → finalized_config extracted, proceeds to DESIGN

**Cycle cap behavior:**
- Code cap hit (code_revision_count >= 2): run.outcome = "partial", return COMPLETE
- Design cap hit (design_revision_count >= 1): falls back to CODE_REVISION if code_revision_count < max; else outcome="partial", COMPLETE

**run() resets all state** — clarification_history, code_revision_count, design_revision_count reset on each call

## How to mock agents for PipelineRunner tests

Use AsyncMock returning valid Pydantic model instances directly — no LLM call needed:

```python
from unittest.mock import AsyncMock, MagicMock
from app.agents.base import BaseAgent

def _make_mock_agent(name, return_value):
    agent = MagicMock(spec=BaseAgent)
    agent.execute = AsyncMock(return_value=return_value)
    return agent

# For multiple return values (side_effect):
qa = MagicMock(spec=BaseAgent)
qa.execute = AsyncMock(side_effect=[qa_review_1, qa_review_2])
```

Pass agents dict to PipelineRunner:
```python
runner = PipelineRunner(
    agents={"requirements_analyst": ra, "solution_architect": sa, "developer": dev, "qa_reviewer": qa},
    emit_event=events.append,  # optional
)
result = await runner.run(customer_config)
```

## PipelineRun fields to assert
- result.state: PipelineState enum
- result.outcome: "success" | "partial" | "failed" | None
- result.completed_at: datetime (set on COMPLETE or FAILED)
- result.feedback_cycles: {"code_revisions": int, "design_revisions": int}
- result.events: list[PipelineEvent] — every emit_event() call appends here
- result.total_tokens: TokenUsage — accumulated from all events with tokens_used
