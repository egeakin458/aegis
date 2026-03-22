---
name: SA methodology step ordering
description: Design steps must follow dependency order — data models before endpoints before UI before file structure — to maintain consistency
type: feedback
---

For the SA prompt, order the methodology steps so each step depends only on previous steps: (1) orientation, (2) requirements inventory, (3) technical constraints, (4) data models, (5) API endpoints, (6) UI components, (7) file structure, (8) dependencies, (9) reasoning. Put "reasoning" in the JSON first (chain-of-thought before decisions) but describe the design process in dependency order.

**Why:** LLMs that design endpoints before data models often produce endpoints that reference non-existent models. Ordering the methodology by dependency flow produces internally consistent designs. The reasoning field appears first in the JSON schema, encouraging the LLM to think before committing to design decisions.

**How to apply:** Use this ordering in the METHODOLOGY section of the SA prompt. For future agents with multi-layer output (design, code, review), always order methodology steps from foundational to dependent.
