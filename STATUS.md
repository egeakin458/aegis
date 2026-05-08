# STATUS

Live project state. Update when work moves.

---

## Current State — 2026-05-08

**8 days to competition (GBYF).**

- Repo: private (`egeakin458/aegis`)
- Backend: offline (Railway service disconnected — config + env vars preserved)
- Frontend: not deployed (Vercel project deleted — will redeploy before demo)
- Tests: 286/286 passing
- Demo plan: run locally on demo day (`uvicorn` + `npm run dev`)

---

## Remaining Work (priority order)

| # | Item | File(s) | Status |
|---|------|---------|--------|
| 6 | Top-level pipeline timeout (`asyncio.wait_for`) | `runner.py` | ☐ |
| 9 | Startup sweep — mark in-flight DB runs as FAILED on restart | `manager.py` / `main.py` | ☐ (only matters if redeploying to Railway) |
| 7 | Tighten Developer prompt: PATCH routing + concrete examples | `developer.py` | ☐ |
| 8 | Post-validate QA verdict consistency | `runner.py`, `agent_outputs.py` | ☐ |
| 10 | Fix `_sanitize_path` with `Path.is_relative_to()` | `output_storage.py` | ☐ |

Plans exist for #6 (`docs/plan_pipeline_timeout.md`). Others need planning.

---

## Demo Day Checklist

- [ ] Run `setup_build_sandbox.sh` on demo machine
- [ ] Set `ANTHROPIC_API_KEY` in local `.env`
- [ ] Run a full pipeline on a simple domain (todo) as rehearsal
- [ ] Have `?run={id}` replay URL ready as fallback
- [ ] Know the `ENABLE_FULL_BUILD_CHECK=false` escape hatch
- [ ] Brief panel: pipeline takes 3–5 min wall-clock

---

## What Shipped

- **Auth** — `Authorization: Bearer` header wired into frontend (REST + SSE + ZIP download); `CustomerConfig` → `CustomerConfigV2` type fix
- **Railway persistent storage** — Volume at `/data`, `init_db()` creates parent dir, `railway.toml` added
- **Build sandbox** — pre-seeded `node_modules` + `better-sqlite3` stub; full build in ~16 s
- **Pipeline Refactor v0.2.0** — state-machine registry, `BUILD_CHECK` state, `CodePatch` patch-based revisions, `feature_id` threading
- **DDC v1** — 4D contract (Actor / DomainEntity / UseCase / BusinessRule) replacing old `CustomerConfig`

---

## Known Issues

- No pipeline timeout — Developer agent can hang 30+ min on complex domains (fix: item #6)
- In-flight runs left as RUNNING in DB after restart (fix: item #9)
- `_sanitize_path` prefix-collision edge case (fix: item #10)
- Context window risk on revisions with complex DDC + large codebases
