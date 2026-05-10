# STATUS

Live state. 6 days to GBYF (2026-05-16).

287/287 unit tests pass. E2E smoke green on `benchmark_02_todo_ddc` (run `ab4f5a1e`, 2026-05-10) — 19 files generated, 100% feature/test score, 231.8 s wall.

---

## Top problems (priority order)

### 1. UI is weak
Functional but visually undercooked. Components feel raw, hierarchy unclear, copy not confident.

**Done =** intake → live feed → output viewer looks intentional on first view.

### 2. UX is bad
Flow has dead ends and confusing states. A first-time viewer does not know what is happening or what to do next.

**Done =** a non-technical viewer can submit, watch, and download an app without a guide.

---

## Smoke regression check

Run before any commit that touches agents, schemas, or the pipeline:

```bash
python evaluation/run_benchmark.py evaluation/benchmarks/benchmark_02_todo_ddc.json
```

Expected: `pipeline_complete`, 100% feature/test score, ~4 min wall.

---

## Code freeze

**2026-05-13.** After that date, no code changes — rehearsal only.

---

## Backlog (post-competition)

Top-level pipeline timeout (#6 — bounds worst-case hang at the pipeline level), Developer prompt PATCH tightening (#7), QA verdict consistency (#8), startup sweep (#9), `_sanitize_path` edge case (#10).

---

## Recently fixed

- **2026-05-10** — `api_timeout` 120 s → 600 s. Developer call measured at 111.5 s on a simple DDC; was running with 7 % headroom under the SDK timeout. Now 5×.
- **2026-05-10** — `evaluation/run_benchmark.py` sends `Authorization: Bearer` header. Was 401-ing against an auth-enabled backend.
- **2026-05-10** — SSE handler dedupes by `event_id` across replay/queue boundary. Early events (e.g. `PIPELINE_STARTED`) were yielded twice; frontend was masking it via its own dedupe.
