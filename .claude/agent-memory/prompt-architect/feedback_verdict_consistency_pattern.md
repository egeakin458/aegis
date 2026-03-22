---
name: Verdict Consistency Pattern
description: QA-style agents with verdict/decision fields must have explicit rules preventing contradictions between findings and verdict
type: feedback
---

When an agent has both a "findings" field (like issues list) and a "decision" field (like verdict), the prompt must include explicit consistency rules:
- "You must NOT approve if critical/major issues exist"
- "Your verdict must be logically consistent with the issues you found"

**Why:** Without these rules, LLMs commonly list problems but then give a positive verdict, likely due to politeness bias or position bias from the reasoning field.

**How to apply:** Any agent prompt that produces both evidence and a judgment must include bi-directional consistency constraints — the judgment must follow from the evidence, AND the evidence must support the judgment.
