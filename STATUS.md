# STATUS

Live project state. Update when work moves.

---

## Current State — 2026-05-10

**6 days to competition (GBYF, 2026-05-16).**

- Repo: private (`egeakin458/aegis`)
- Backend: offline (Railway service disconnected — config + env vars preserved)
- Frontend: not deployed (Vercel project deleted — will redeploy before demo)
- Tests: 286/286 passing
- Demo plan: run locally on demo day (`uvicorn` + `npm run dev`)

**Operating mode: Demo Week.** Skip `/plan-next` ceremony until 2026-05-19. Implement small fixes straight. Poster + rehearsal are first-class work, not background.

---

## Demo Week Schedule

| Date | T-? | Focus | Status |
|------|-----|-------|--------|
| 2026-05-10 (today) | T-6 | Ship #6 pipeline timeout (plan exists at `docs/plan_pipeline_timeout.md`) | ☐ |
| 2026-05-11 | T-5 | Poster v1 draft (`PosterPlani.md` → `Poster/`) | ☐ |
| 2026-05-12 | T-4 | Smoke-test full pipeline on demo machine + 5-min talk script | ☐ |
| 2026-05-13 | T-3 | **CODE FREEZE.** Rehearsal #1 (record yourself). | ☐ |
| 2026-05-14 | T-2 | Poster final + QR card printed. Rehearsal #2. | ☐ |
| 2026-05-15 | T-1 | Rehearsal #3, dry run on demo machine. | ☐ |
| 2026-05-16 | T-0 | **Demo.** | ☐ |

After 2026-05-13: zero code changes. Bug found = note it, don't fix it.

---

## Active Work — Demo Blocker

| # | Item | File(s) | Status |
|---|------|---------|--------|
| 6 | Top-level pipeline timeout (`asyncio.wait_for`) — Developer can hang 30+ min mid-demo | `runner.py` | ☐ |

Plan exists: `docs/plan_pipeline_timeout.md`. Implement straight from it — no re-planning.

---

## Demo Day Checklist

- [ ] Run `setup_build_sandbox.sh` on demo machine
- [ ] Set `ANTHROPIC_API_KEY` in local `.env`
- [ ] Run a full pipeline on a simple domain (todo) as rehearsal
- [ ] Have `?run={id}` replay URL ready as fallback
- [ ] Know the `ENABLE_FULL_BUILD_CHECK=false` escape hatch
- [ ] Brief panel: pipeline takes 3–5 min wall-clock

---

## Post-Competition Backlog

Resume after 2026-05-19. Re-enable `/plan-next` workflow then.

| # | Item | File(s) |
|---|------|---------|
| 9 | Startup sweep — mark in-flight DB runs as FAILED on restart (only matters if redeploying to Railway) | `manager.py` / `main.py` |
| 7 | Tighten Developer prompt: PATCH routing + concrete examples | `developer.py` |
| 8 | Post-validate QA verdict consistency | `runner.py`, `agent_outputs.py` |
| 10 | Fix `_sanitize_path` with `Path.is_relative_to()` | `output_storage.py` |

---

## What Shipped

- **Auth** — `Authorization: Bearer` header wired into frontend (REST + SSE + ZIP download); `CustomerConfig` → `CustomerConfigV2` type fix
- **Railway persistent storage** — Volume at `/data`, `init_db()` creates parent dir, `railway.toml` added
- **Build sandbox** — pre-seeded `node_modules` + `better-sqlite3` stub; full build in ~16 s
- **Pipeline Refactor v0.2.0** — state-machine registry, `BUILD_CHECK` state, `CodePatch` patch-based revisions, `feature_id` threading
- **DDC v1** — 4D contract (Actor / DomainEntity / UseCase / BusinessRule) replacing old `CustomerConfig`

Shipped-feature plans archived under `docs/archive/` (kept as thesis methodology evidence).

---

## Known Issues

- No pipeline timeout — Developer agent can hang 30+ min on complex domains (fix: item #6 — **demo blocker**)
- In-flight runs left as RUNNING in DB after restart (fix: item #9 — post-competition)
- `_sanitize_path` prefix-collision edge case (fix: item #10 — post-competition)
- Context window risk on revisions with complex DDC + large codebases
