---
name: Audit Round 2 Findings
description: Results of the second schema consistency audit (all 4 agents implemented). One breaking issue found and fixed in runner.py.
type: project
---

Audit performed 2026-03-21 after all four agents were implemented.

**Fixed:** `backend/app/pipeline/runner.py` `_run_requirements()` — added a None guard on `result.finalized_config` before accessing `finalized.project_summary`. Without the guard, if the LLM returns `needs_clarification=True` after the clarification round cap is hit, the runner crashes with `AttributeError` on `None`.

**Why:** `RAOutput.finalized_config` is `Optional[FinalizedConfig]` and is only guaranteed non-None when `needs_clarification=False` (enforced by `model_validator`). The runner's cap-handling path (`at_round_cap=True`) forces `mode="finalize"` but can't prevent a misbehaving LLM from still returning `needs_clarification=True`. The old code fell through the clarification branch check and accessed `finalized_config` without a guard.

**How to apply:** Any future code that reads `RAOutput.finalized_config` must check for `None` first, even if the surrounding context implies the RA was told to finalize.

**Everything else passed:**
- All schema exports in `app/schemas/__init__.py` are complete — all 44 public symbols across 5 schema files are re-exported.
- All 4 agent classes exported from `app/agents/__init__.py`.
- All context keys provided by PipelineRunner exactly match what each agent's `build_user_prompt()` reads.
- All EventType enum values used in runner.py and base.py exist in the EventType enum.
- All field accesses on schema objects in runner.py are on required (non-Optional) fields.
- SA revision context: runner passes `previous_design` + `qa_review`; SA checks `"previous_design" in context` — key names match exactly.
- Dev revision context: runner passes `previous_code` + `qa_review`; Dev checks `"previous_code" in context` — key names match exactly.
