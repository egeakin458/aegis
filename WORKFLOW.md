# WORKFLOW

How to ship features, updates, and fixes in this codebase. Read `CLAUDE.md` and `STATUS.md` first.

---

## Pick the mode (one question)

| Situation | Mode |
|---|---|
| You're fixing a bug | **DEBUG** |
| You know what to build | **PLAN** |
| You don't know yet | **SPIKE** |

Pick one before you start. Most work is PLAN.

---

## PLAN MODE — when you know what to build

A senior model writes a detailed plan file. A fresh chat with a weaker model executes it line-by-line. The plan is a saved file, not chat history.

**The plan must contain:**
- Goal (one sentence)
- The commit SHA it was written against
- Step-by-step actions, each ending in a git commit
- A verify block per step (command that proves it worked)
- "What can go wrong" table — symptom → action
- Two-strike rule: if a step fails twice after fixes, the executor stops and surfaces it

**Execution chat (fresh, weaker model):**
```
Read CLAUDE.md, STATUS.md, and the plan at <path>. Execute it exactly. Stop after each commit so I can verify.
```

After commit ~3 of N, read the diff with fresh eyes. If it looks wrong, redirect before later commits cement it.

**If the change touches any contract** (schema, API endpoint, event type, agent output): the plan MUST cover the Contract Change Checklist below. No exceptions.

---

## SPIKE MODE — when you don't know the shape

Throwaway chat, throwaway branch. Goal is to learn, not to ship.

1. `git checkout -b spike/<thing>`
2. Build the ugliest version that answers your question
3. Write a one-page memo: what works, what doesn't, what to actually build
4. `git checkout main && git branch -D spike/<thing>` — throw it away
5. Now you're in PLAN MODE — write a real plan against `main`

The throw-away is the point. Cheaper to discard once than to refactor four times.

---

## DEBUG MODE — when something is broken

Don't plan a fix. Investigate first.

1. **Reproduce it.** If you can't reproduce, you can't fix.
2. **Write a failing test** that captures the bug.
3. **State a hypothesis.** "I think X happens because Y."
4. **Verify the hypothesis** with the smallest possible probe — a print, a debugger, a one-line change.
5. **Only after diagnosis is confirmed**, write the fix and commit.

Tell Claude explicitly: *"Diagnose the root cause. Don't patch symptoms."* Otherwise it'll propose workarounds that paper over the real bug.

---

## Contract Change Checklist (Aegis-specific, non-negotiable)

A contract change ripples through the whole stack. Skipping any point = silent runtime breakage. Every plan touching a schema MUST check all 8:

1. `backend/app/schemas/*.py` — Pydantic source of truth
2. `frontend/lib/schemas/*.ts` — Zod mirror (`npm run gen:types` or hand-edit)
3. Every agent's system prompt + `build_user_prompt()` — does the agent see/produce the new field?
4. `frontend/lib/mappers/*.ts` — Quick AND Advanced both produce the new shape
5. `backend/tests/fixtures/*.json` — fixtures still parse
6. `app/pipeline/manager.py` — context dict passes the new field through
7. `STATUS.md` — note the contract change
8. Migration plan (or explicit "throw away `aegis.db`")

If any point is missing from the plan, the plan is incomplete.

---

## Universal rules (every mode)

- **One feature = one branch.** Named `feat/<thing>`, `fix/<thing>`, or `spike/<thing>`.
- **Atomic commits.** Tree is green at every commit. No "WIP" or "fix typo" commits — squash or fixup before merging.
- **`STATUS.md` updated twice:** when you start (move to "Current Focus"), when you finish (move to "Recently Shipped").
- **`CLAUDE.md` updated only on architectural change.** New schema field doesn't update it; new pipeline state does.
- **Memory updated only when something is non-obvious** — a gotcha, a convention, a surprising decision.
- **Smoke test before merging to `main`:** one benchmark run with `ENABLE_FULL_BUILD_CHECK=true`. Unit tests are necessary but not sufficient.
- **Merge directly to `main` only after smoke + atomic commits + STATUS update.** No untested branches on `main`.

---

## When to skip the ceremony

- Diff <100 lines, one file, well-understood → just implement, no plan needed.
- Thesis demo / research spike → flex everything *except* the Contract Change Checklist.
- The Contract Change Checklist is non-negotiable. Always.

---

## Kickoff prompt for new feature/fix sessions

Paste this in a fresh chat:

```
Read CLAUDE.md, STATUS.md, and WORKFLOW.md.
I want to <one sentence>. Constraint: <one sentence>.
Pick the mode (PLAN / SPIKE / DEBUG), then ask me 3 questions before proposing anything.
```

The "ask me 3 questions" line forces Claude to surface its assumptions before committing to a direction. That's the highest-leverage moment.
