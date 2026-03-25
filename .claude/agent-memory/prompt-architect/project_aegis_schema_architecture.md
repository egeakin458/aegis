---
name: Aegis schema and pipeline architecture summary
description: Key schema relationships and pipeline data flow for designing agent prompts
type: project
---

The Aegis pipeline has 4 agents with this data flow: CustomerConfig -> RA -> FinalizedConfig -> SA -> TechnicalDesign -> Dev -> CodeOutput -> QA -> QAReview.

Key schema facts for prompt design:
- FinalizedConfig wraps a CustomerConfig (refined copy) + assumptions + clarification_history + project_summary + is_complete
- TechnicalDesign, CodeOutput, and QAReview all have a "reasoning" field for chain-of-thought; FinalizedConfig does NOT (project_summary and assumptions serve this role instead)
- The RA has a dual-output problem: clarification questions vs. FinalizedConfig — no wrapper model exists in the schema yet
- BaseAgent retries ONCE on validation failure by appending the error to the user message
- System prompt is passed via the Anthropic API's "system" parameter with cache_control ephemeral
- max_clarification_rounds = 3 (from config.py settings)

**Why:** Understanding these relationships is essential for designing prompts that correctly describe input/output schemas and role boundaries.

**How to apply:** Always read the actual schema files before designing a prompt. Reference this memory for quick orientation on which schemas connect to which agents.
