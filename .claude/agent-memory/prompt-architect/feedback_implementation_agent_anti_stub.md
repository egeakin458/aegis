---
name: Anti-Stub Constraint for Implementation Agents
description: Developer/implementation agents need explicit prohibition against placeholder code, TODO comments, and stub functions
type: feedback
---

Implementation agents (Developer) must include an explicit constraint against stub/placeholder code. LLMs generating code default to producing skeletons with TODO comments when output length is constrained or the task is complex.

**Why:** The Developer agent's output goes directly to QA and potentially to the customer. Stubs masquerading as implementations waste a review cycle and produce a non-functional deliverable.

**How to apply:** Include both a "must NOT" constraint ("Do not produce stub or placeholder code") AND positive quality criteria ("Every function must have a real implementation"). Also require that if something was genuinely simplified, it goes in known_limitations rather than being silently stubbed.
