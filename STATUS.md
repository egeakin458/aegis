# STATUS

Live state. 6 days to GBYF (2026-05-16).

286/286 unit tests pass — but E2E has never been observed green.

---

## Top problems (priority order)

### 1. End-to-end pipeline does not complete
Latest retry died at the Developer stage — agent hit a per-call time limit.
No green run on `benchmark_02_todo_ddc` to date.

Smoke command:
```bash
python evaluation/run_benchmark.py evaluation/benchmarks/benchmark_02_todo_ddc.json
```

**Done =** one full run reaches `PIPELINE_COMPLETE`, generated app passes `next build`.

### 2. UI is weak
Functional but visually undercooked. Components feel raw, hierarchy unclear, copy not confident.

**Done =** intake → live feed → output viewer looks intentional on first view.

### 3. UX is bad
Flow has dead ends and confusing states. A first-time viewer does not know what is happening or what to do next.

**Done =** a non-technical viewer can submit, watch, and download an app without a guide.

---

## Code freeze

**2026-05-13.** After that date, no code changes — rehearsal only.

---

## Backlog (post-competition)

Pipeline timeout (#6 — to be replanned, likely fix for problem #1), Developer prompt PATCH tightening (#7), QA verdict consistency (#8), startup sweep (#9), `_sanitize_path` edge case (#10).
