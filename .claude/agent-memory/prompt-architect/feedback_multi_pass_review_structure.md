---
name: Multi-Pass Review Structure
description: QA agents should be given named review passes that map directly to issue category values
type: feedback
---

When a review agent categorizes issues (e.g., "functional", "requirements_alignment", "code_quality", "security"), structure the methodology as named passes that correspond 1:1 to those categories. Each pass gets its own checklist of what to examine.

**Why:** This prevents the agent from doing a single undifferentiated scan and ensures coverage across all dimensions. It also naturally produces issues with the correct category since the agent knows which pass it's in.

**How to apply:** Name each pass after the category value, give each pass specific checkpoints, and instruct the agent to assign the category based on which pass surfaced the issue.
