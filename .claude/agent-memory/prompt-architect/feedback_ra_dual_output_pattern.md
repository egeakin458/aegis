---
name: RA dual-output prompt pattern
description: Design pattern for agents that produce different JSON shapes depending on mode, with mode selected via user message
type: feedback
---

When an Aegis agent has multiple output modes (like the RA's clarification vs. finalization), describe ALL output shapes in the system prompt under clearly labeled mode headers (e.g., "MODE A", "MODE B"). The user message (built by build_user_prompt) selects which mode is active. This aligns with Claude API design: system = persistent capability, user = task trigger.

**Why:** The BaseAgent validates against a single output_schema, so the implementation will need a wrapper/union model. The system prompt must make both shapes crystal clear so the LLM picks the right one on the first attempt (only 1 retry available).

**How to apply:** For any future multi-mode agent, use this structure: describe all modes in [OUTPUT FORMAT] with explicit mode labels, then reference "the task you receive will specify which mode" to defer mode selection to the user message.
