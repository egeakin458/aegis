---
name: Threshold test pattern for RA question quality
description: The "would the answer materially change what gets built?" test prevents trivial clarification questions
type: feedback
---

For the Requirements Analyst, instruct it to apply a "threshold test" before asking any clarification question: "Would the answer materially change what gets built?" This prevents the common LLM failure mode of asking exhaustive, trivial questions that frustrate non-technical users.

**Why:** Without this constraint, LLMs default to being thorough by asking about everything, including cosmetic details and edge cases that don't affect architecture. This creates a poor customer experience and wastes clarification rounds.

**How to apply:** Include this test in the METHODOLOGY section of the RA prompt. Also reinforce it in CONSTRAINTS ("must NOT ask trivial questions") and QUALITY CRITERIA ("weak output = questions about cosmetic details").
