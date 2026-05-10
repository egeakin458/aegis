# STATUS

Live project state. Update when work moves.

---

## Current State — 2026-05-10

**6 days to competition (GBYF, 2026-05-16).**

- Repo: private (`egeakin458/aegis`)
- Backend: offline (Railway service disconnected — config + env vars preserved)
- Frontend: not deployed (Vercel project deleted — will redeploy before demo)
- Unit tests: 286/286 passing
- **End-to-end pipeline: not yet validated.** No green smoke run on record.
- Demo plan: run locally on demo day (`uvicorn` + `npm run dev`)

**Operating mode: Demo Week.** Skip `/plan-next` ceremony until 2026-05-19. Two workstreams in parallel: (A) prove the system works end-to-end, (B) tighten frontend UX. Everything else waits.

---

## The Two Real Blockers

### (A) End-to-end pipeline must produce a working app on `benchmark_02_todo_ddc`

286 unit tests pass, but the full pipeline (RA → SA → Dev → BuildCheck → QA → output) has never been observed completing successfully on a real benchmark. Until it does, nothing else matters.

Smoke test infrastructure exists — the gap is a green run.

```bash
# Backend running on :8000, then:
python evaluation/run_benchmark.py evaluation/benchmarks/benchmark_02_todo_ddc.json
```

**Definition of done:** one full run on `benchmark_02_todo_ddc` ends in `PIPELINE_COMPLETE`, `outputs/{run_id}/` contains a Next.js app, and that app passes `next build`.

### (B) Frontend UX

Current frontend works mechanically but the UX is not demo-ready. Needs a focused polish pass — not a redesign.

**Definition of done:** intake → live SSE feed → output viewer feels coherent and confident on a fresh viewer's first try. No dead ends, no jank, no jargon-laden copy.

---

## Demo Week Schedule

| Date | T-? | Workstream A — pipeline correctness | Workstream B — frontend UX | Status |
|------|-----|-------------------------------------|----------------------------|--------|
| 2026-05-10 (today) | T-6 | Reproduce E2E run on `benchmark_02_todo_ddc`. **Characterize the failure mode** (where it fails, what symptom). | UX audit: list every screen, every dead end, every confusing copy line. | ☐ |
| 2026-05-11 | T-5 | Fix root cause(s) of E2E failure. | UX iteration #1 (top 3 audit items). | ☐ |
| 2026-05-12 | T-4 | E2E re-run on `benchmark_02_todo_ddc`. Must end green. | UX iteration #2 (next 3 items) + 5-min talk script. | ☐ |
| 2026-05-13 | T-3 | **CODE FREEZE.** Full E2E rehearsal end-to-end. Record. | Final polish only — no new components. | ☐ |
| 2026-05-14 | T-2 | Rehearsal #2 on demo machine. Bug-watch only — no fixes. | Bug-watch only. | ☐ |
| 2026-05-15 | T-1 | Dry run #3, full demo machine setup verified. | — | ☐ |
| 2026-05-16 | T-0 | **Demo.** | — | ☐ |

After 2026-05-13 (T-3): zero code changes. Bug found = note it, don't fix it.

---

## Hardening Items — Triage Against (A)

These were the original "Remaining Work" list. Until E2E is characterized, we don't know which (if any) are causing the failure. Most likely none of them are.

| # | Item | File(s) | Likely relevant to E2E failure? |
|---|------|---------|--------------------------------|
| 6 | Top-level pipeline timeout (`asyncio.wait_for`) | `runner.py` | If failure mode is "Developer hangs", **yes** — fold into (A). Otherwise post-competition. |
| 7 | Tighten Developer prompt: PATCH routing + concrete examples | `developer.py` | If Developer produces invalid patches, **yes**. Otherwise post-competition. |
| 8 | Post-validate QA verdict consistency | `runner.py`, `agent_outputs.py` | Only if QA verdict is the failure surface. Likely post-competition. |
| 9 | Startup sweep — mark in-flight DB runs as FAILED on restart | `manager.py` / `main.py` | Only relevant on Railway. Post-competition. |
| 10 | Fix `_sanitize_path` with `Path.is_relative_to()` | `output_storage.py` | Edge case. Post-competition. |

Decide each item's fate **after** today's failure characterization, not before.

---

## Demo Day Machine Checklist

To run on the demo laptop the day before (T-1):

- [ ] Run `setup_build_sandbox.sh` on demo machine
- [ ] Set `ANTHROPIC_API_KEY` in local `.env` (verify credit balance)
- [ ] `?run={id}` replay URL ready as fallback
- [ ] `ENABLE_FULL_BUILD_CHECK=false` escape hatch known and tested
- [ ] Backup pre-recorded run video on USB
- [ ] Brief panel: pipeline takes 3–5 min wall-clock

---

## What Shipped

- **Auth** — `Authorization: Bearer` wired into frontend (REST + SSE + ZIP); `CustomerConfig` → `CustomerConfigV2` type fix
- **Railway persistent storage** — Volume at `/data`, `init_db()` creates parent dir, `railway.toml` added
- **Build sandbox** — pre-seeded `node_modules` + `better-sqlite3` stub; full build in ~16 s
- **Pipeline Refactor v0.2.0** — state-machine registry, `BUILD_CHECK` state, `CodePatch` patch-based revisions, `feature_id` threading
- **DDC v1** — 4D contract (Actor / DomainEntity / UseCase / BusinessRule) replacing old `CustomerConfig`

Shipped-feature plans archived under `docs/archive/` (kept as thesis methodology evidence).

---

## Known Issues

- **No validated E2E run** — see workstream (A) above. **Top blocker.**
- **Frontend UX not demo-ready** — see workstream (B) above.
- No pipeline timeout — Developer can hang 30+ min on complex domains (item #6, fold into A if relevant)
- In-flight runs left as RUNNING in DB after restart (item #9, post-competition)
- `_sanitize_path` prefix-collision edge case (item #10, post-competition)
- Context window risk on revisions with complex DDC + large codebases
