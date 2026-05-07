# /plan-next

Pick the top unchecked item from the Priority List in `STATUS.md`, then use the lead-engineer agent to write a full implementation plan for it. Save the plan to `docs/plan_<slug>.md`.

## Steps

1. Read `STATUS.md`. Find the first row in the Priority List table whose Status cell is `☐`. That is the item to plan. Note its number, title, and affected files.

2. Read any files listed in the item's "File(s)" column so you understand what currently exists.

3. Spawn the lead-engineer agent with the full brief below. Pass it the item title, affected files, and any relevant context you gathered from reading the codebase. The agent must **only write the plan doc** — no implementation.

## Lead-engineer brief to include verbatim

> Write a comprehensive implementation plan for: **[ITEM TITLE]**
>
> Save it to `docs/plan_[slug].md` (repo root `/home/ege/projects/aegis`). Do NOT implement any code — only produce the plan document.
>
> ### Planning rules (follow exactly)
>
> **Format:**
> ```
> # Plan: [Title]
> **Written against:** `main` @ [run: git -C /home/ege/projects/aegis rev-parse --short HEAD]
> **Goal:** one sentence
> ---
> ## Background (read this before starting)
> [What exists today — exact file paths and line numbers. What the fix must do. Gotchas and compatibility notes.]
> ---
> ### Task N: [Component Name]
> **Files:**
> - Create: `exact/path/to/file.py`
> - Modify: `exact/path/to/existing.py`
> - [ ] **Step 1: ...**
> ...
> ```
>
> **Step granularity — each step is one action (2–5 min):**
> - "Write the failing test" — show full test code
> - "Run it to verify it fails" — show exact command + expected failure message
> - "Write minimal implementation" — show full code
> - "Run to verify it passes" — show exact command + expected output
> - "Commit" — show exact `git add` + `git commit -m "..."` command
>
> **Code rules:**
> - Every step that involves code must show the **complete** code — no `...` or "similar to above"
> - No placeholders: no "TODO", "TBD", "add appropriate validation", "handle edge cases"
> - Exact file paths always
> - TDD: tests before implementation
> - DRY, YAGNI — only what is needed for this specific fix
> - Frequent commits — one commit per logical unit
>
> **No placeholder failures** — these are plan failures, never write them:
> - "TBD", "TODO", "implement later"
> - "Add appropriate error handling" / "handle edge cases"
> - "Write tests for the above" (without actual test code)
> - "Similar to Task N" (repeat the code — the engineer may read tasks out of order)
> - Steps that describe what to do without showing how
>
> **Compatibility:** when changing existing code, consider backward compatibility and document it explicitly in the Background section.
>
> **Scope check:** if the item covers multiple independent subsystems, say so at the top and suggest breaking it into sub-plans.
>
> **What to cover (always include):**
> 1. TDD red step — failing tests first, full test code, exact run command + expected failure
> 2. Implementation — minimal code to make tests pass
> 3. Regression — run full test suite, show command + expected output
> 4. Docs — update `.env.example` if new env vars are added
> 5. STATUS.md — mark the item complete (show exact edit + commit)
>
> **Test fixture convention for this repo:** all `backend/tests/` test files need an autouse `mock_db` fixture that patches `app.main.init_db`, `app.main.close_db`, `app.main.settings`, AND `app.api.auth.settings` with `api_key=""`. Mirror this exactly from `backend/tests/test_api.py` lines 24-34. Failing to include it causes 401s or DB errors on every test.
>
> **Confirm the plan was written** — respond with a one-paragraph summary of what it covers. Do not print the full plan.

## After the agent finishes

Confirm the plan file was written at the expected path, then tell the user:
- Which item was planned (number + title)
- Where the plan was saved
- One-sentence summary of what it covers
- "Run `/start-next` to execute it" (or just say they can start with "You can start.")
