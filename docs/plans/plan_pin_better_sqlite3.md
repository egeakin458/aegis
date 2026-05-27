# PLAN — Pin better-sqlite3 to ^11.0.0 for Node 22+ compat

**Goal:** Make the Developer agent reliably emit `better-sqlite3: "^11.0.0"` in generated `package.json` so customer apps install fine on Node ≥22.

**Written against:** `3c364ff` (main).

**Mode:** PLAN. Single source of behaviour change: the Developer agent's system prompt. The build sandbox is already on `11.1.2` so no sandbox rebuild is strictly required, but Step 2 verifies that. `_ALLOWED_DEPS` is name-only (no version field) and does not need to change.

**Backlog item:** #11 (STATUS.md).

---

## Background

The current Developer prompt (`backend/app/agents/developer.py`, lines ~33–77) declares the fixed tech stack but **never pins a version for any dep**. Empirically the agent fabricates a different version per run:

| Run | Date | better-sqlite3 emitted |
|---|---|---|
| `2f9efe31`, `e9de0368` | ~2026-05-02..04 | `^9.6.0` |
| `f4b4517a` (guestbook) | 2026-05-11 | `^11.10.0` |
| `d40f9c05` (today) | 2026-05-27 | `^9.4.3` |

`^9.x` fails to compile on Node ≥22 due to V8 API changes — the bug `STATUS.md` backlog #11 calls out. The build sandbox masks this because it hardlinks pre-installed `node_modules` (already on `11.1.2`) instead of running `npm install`. So today the build check passes regardless of the version in the generated `package.json`. Failure only surfaces at *customer* install time on a Node ≥22 machine.

---

## Steps

### Step 1 — Pin the version in the Developer prompt

**Files:** `backend/app/agents/developer.py`

**Change:** In the "FIXED TECHNOLOGY STACK" block, replace

```
- package.json MUST include: "next": "14.x.x", "better-sqlite3", "tailwindcss", "postcss", "autoprefixer"
```

with

```
- package.json MUST include: "next": "14.x.x", "better-sqlite3": "^11.0.0", "tailwindcss", "postcss", "autoprefixer"
- The better-sqlite3 version pin is mandatory: versions <11 fail to compile on Node ≥22.
```

Also tighten Step 5 in METHODOLOGY for consistency:

```
Step 5 — Implement package.json with next@14, better-sqlite3@^11.0.0, tailwindcss, postcss, autoprefixer.
```

**Why a caret pin (not exact):** customer `npm install` should pull the latest patch/minor 11.x at install time without code changes. The sandbox uses exact `11.1.2`, which is within `^11.0.0`, so build checks remain valid.

**Verify:**
```bash
grep -n "better-sqlite3" backend/app/agents/developer.py
# Expected: at least one line with "better-sqlite3": "^11.0.0"
```

**Commit:** `fix(developer): pin better-sqlite3@^11.0.0 to avoid Node 22+ incompat`

---

### Step 2 — Confirm sandbox already on 11.x

**Files:** `backend/build_sandbox/package.json` (read-only check).

**Verify:**
```bash
python3 -c "import json; v=json.load(open('backend/build_sandbox/package.json'))['dependencies']['better-sqlite3']; assert v.startswith('11.'), v; print('sandbox better-sqlite3:', v)"
```

Expected: `sandbox better-sqlite3: 11.1.2` (or any other 11.x exact).

If the sandbox is NOT on 11.x: edit `backend/build_sandbox/package.json` to `"better-sqlite3": "11.1.2"`, then:

```bash
bash backend/scripts/setup_build_sandbox.sh --force
```

Verify after rebuild:
```bash
node -e "console.log(require('./backend/build_sandbox/node_modules/better-sqlite3/package.json').version)"
# Expected: 11.x.x
```

**Commit (only if sandbox was changed):** `chore(sandbox): pin better-sqlite3@11.1.2 in build sandbox`

---

### Step 3 — Run unit tests

```bash
cd backend && source venv/bin/activate && pytest tests/ -q
```

Expected: 288/288 pass, no new failures. The prompt change is text-only so most tests are unaffected; tests that snapshot the Developer prompt (if any) may need re-recording.

**No commit unless tests changed.**

---

### Step 4 — Run E2E smoke and verify the pin took

```bash
# Terminal 1, from backend/
ENABLE_FULL_BUILD_CHECK=true uvicorn app.main:app --port 8000

# Terminal 2, from repo root
API_KEY="$(grep ^API_KEY= backend/.env | cut -d= -f2-)" python3 evaluation/run_benchmark.py evaluation/benchmarks/benchmark_02_todo_ddc.json
```

Expected: `pipeline_complete`, 100% feature/test score, ~5 min wall.

**Verify the pin landed in the generated app:**
```bash
LATEST=$(ls -t backend/outputs/ | head -1)
python3 -c "import json; pkg=json.load(open(f'backend/outputs/$LATEST/package.json')); v=pkg['dependencies']['better-sqlite3']; assert v.startswith('^11'), v; print('emitted:', v)"
# Expected: emitted: ^11.0.0  (or ^11.x.y)
```

**Update STATUS.md:**

- Move backlog item #11 to "Recently fixed".
- New entry under "Recently fixed":
  ```
  - **2026-05-27** — better-sqlite3 pinned to ^11.0.0 in Developer prompt (backlog #11). Generated apps now install cleanly on Node ≥22. Sandbox already on 11.1.2; build check unchanged. Smoke-verified on benchmark_02_todo_ddc (run <new_run_id>).
  ```

**Commit:** `chore(status): close backlog #11 — better-sqlite3 pinned`

---

## What can go wrong

| Symptom | Action |
|---|---|
| `pytest` fails on a prompt snapshot test | Re-record the snapshot if the diff is just the new version-pin line. If broader, stop — surface to me. |
| Step 4 generated `package.json` has `^9.x` again | Agent ignored the pin. Strengthen prompt: put the version requirement in CONSTRAINTS section (Do NOT use better-sqlite3 versions <11; the build sandbox only supports 11.x). Re-run smoke. |
| Step 4 smoke fails on build_check with new dep drift | Check the issue list — if it's a new dep we don't allowlist, extend `_ALLOWED_DEPS` + sandbox. If it's a version mismatch, the agent emitted a version the sandbox can't resolve via hardlinks (unlikely — hardlinks ignore package.json version). |
| Sandbox rebuild errors out | Rare. Check `backend/scripts/setup_build_sandbox.sh` output. Last-resort: `--force` rebuild deletes `node_modules` and reinstalls fresh; if that fails, `npm` may need updating on the host. |
| Smoke run takes >7 min | Anthropic API latency. Re-run once. If second attempt also slow, surface — not a Step 4 problem. |

**Two-strike rule:** if any step fails twice after fixes, stop and surface.

---

## Contract Change Checklist

This is a prompt + config change, not a schema change. The 8-point Contract Change Checklist (`WORKFLOW.md`) does NOT apply in full. The only checklist items in play:

- ✅ Agent system prompt updated (`developer.py`, Step 1).
- ✅ STATUS.md updated (Step 4).
- ❌ Pydantic schemas — not touched.
- ❌ Zod mirror — not touched.
- ❌ Frontend mappers — not touched.
- ❌ Backend fixtures — not touched.
- ❌ `manager.py` context dict — not touched.
- ❌ Migration plan — no DB schema change.

No migration required.
