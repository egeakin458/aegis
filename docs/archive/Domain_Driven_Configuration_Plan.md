# Domain-Driven Configuration (DDC) — Implementation-Ready Plan

> **Status:** Approved 2026-05-03. Supersedes the previous draft. The implementation will be executed by a less-capable model, so every step must be unambiguous.

---

## 1. Context and Goal

The current `CustomerConfig` (`backend/app/schemas/customer_config.py`) is too conversational and inconsistent for deterministic code generation. Field semantics drift between agents; the LLM occasionally hallucinates relationships that aren't in the config; the Solution Architect must infer database types from free-text data names.

DDC replaces the conversational intake with a **strict 4-dimensional contract** (Who / What / Why+How) that is directly machine-actionable. The new schema is the canonical input the entire pipeline consumes.

**Non-goals of this phase:** auth implementation in generated apps (still constrained to `better-sqlite3` + Next.js 14 App Router as before); changes to the runner state machine; changes to the BUILD_CHECK or CodePatch logic.

---

## 2. Final Pydantic Contract

This is the **complete** schema. It supersedes the previous draft and incorporates fixes for the 9 weaknesses identified during review.

```python
# backend/app/schemas/customer_config.py
from pydantic import BaseModel, Field, model_validator
from typing import List, Literal, Optional
import uuid

# --- 2.1 Enums ---

AuthMethod = Literal["anonymous", "email_password", "invite_only", "sso"]
UseCaseType = Literal["command", "query"]
DataFieldType = Literal["string", "text", "integer", "decimal", "boolean", "datetime", "date", "uuid", "json"]
RelationshipKind = Literal["one_to_one", "one_to_many", "many_to_many"]
Industry = Literal["retail", "healthcare", "education", "finance", "services", "other"]
VisualStyle = Literal["clean_minimal", "bold_modern", "warm_friendly", "professional_corporate", "playful"]

# --- 2.2 Atoms ---

class Attribute(BaseModel):
    """A typed property of a DomainEntity. Reuses Phase-3 typed schemas."""
    name: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$",
                      description="snake_case attribute name. Becomes a SQL column.")
    type: DataFieldType = Field(..., description="Maps directly to a SQLite column type.")
    required: bool = Field(default=True)
    unique: bool = Field(default=False)
    description: Optional[str] = Field(None, max_length=200,
                                       description="Optional human note for the SA's UI rendering.")

class Relationship(BaseModel):
    """Entity-to-entity relationship. Drives FK creation by the SA."""
    id: str = Field(default_factory=lambda: f"rel_{uuid.uuid4().hex[:8]}")
    from_entity_id: str = Field(..., description="References DomainEntity.id (the owning side).")
    to_entity_id: str = Field(..., description="References DomainEntity.id (the related side).")
    kind: RelationshipKind
    name: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$",
                      description="snake_case role name, e.g. 'order_items', 'author'.")

# --- 2.3 Core Dimensions ---

class ProjectContext(BaseModel):
    name: str = Field(..., min_length=2, max_length=60,
                      description="Kebab-case basis for project naming.")
    domain_description: str = Field(..., min_length=50, max_length=1500,
                                    description="Core business value. SA infers tone and UX from this.")
    industry: Industry
    visual_style: VisualStyle = Field(default="clean_minimal",
                                      description="Tailwind theme hint for the Developer agent.")
    mobile_first: bool = Field(default=True)

class Actor(BaseModel):
    """The 'WHO'. RBAC subject."""
    id: str = Field(default_factory=lambda: f"act_{uuid.uuid4().hex[:8]}")
    role_name: str = Field(..., pattern=r"^[A-Z][a-zA-Z0-9]*$",
                           description="PascalCase role, e.g. 'SystemAdmin', 'Customer'.")
    auth_method: AuthMethod
    permissions_description: str = Field(..., min_length=10, max_length=500,
                                         description="Free-text capability summary; QA reads this.")

class DomainEntity(BaseModel):
    """The 'WHAT'. Source of truth for DDL generation."""
    id: str = Field(default_factory=lambda: f"ent_{uuid.uuid4().hex[:8]}")
    name: str = Field(..., pattern=r"^[A-Z][a-zA-Z0-9]*$",
                      description="Singular PascalCase, e.g. 'Invoice', 'PatientRecord'.")
    attributes: List[Attribute] = Field(..., min_length=1)
    states: List[str] = Field(default_factory=lambda: ["Active"], min_length=1,
                              description="Lifecycle states; mapped to a CHECK constraint.")
    owned_by_actor_id: Optional[str] = Field(None,
                                             description="References Actor.id. Implies an FK to that actor.")

class BusinessRule(BaseModel):
    """The 'WHY/HOW'. Top-level so it can be referenced by many UseCases."""
    id: str = Field(default_factory=lambda: f"rule_{uuid.uuid4().hex[:8]}")
    description: str = Field(..., min_length=10, max_length=500,
                             description="Human-readable; QA asserts against this.")
    trigger_condition: str = Field(..., max_length=300,
                                   description="e.g. 'When Order.state == Pending'.")
    enforcement_action: str = Field(..., max_length=300,
                                    description="e.g. 'Reject mutation, return 400'.")

class UseCase(BaseModel):
    """The 'HOW'. Connects an Actor to an Entity through Rules."""
    id: str = Field(default_factory=lambda: f"uc_{uuid.uuid4().hex[:8]}")
    name: str = Field(..., min_length=3, max_length=80,
                      description="Imperative verb phrase, e.g. 'Process Refund'.")
    type: UseCaseType
    actor_id: str = Field(..., description="References Actor.id.")
    primary_entity_id: str = Field(..., description="References DomainEntity.id.")
    business_rule_ids: List[str] = Field(default_factory=list,
                                          description="References BusinessRule.id values.")
    description: Optional[str] = Field(None, max_length=400,
                                       description="Optional context for the SA.")

# --- 2.4 Root Payload ---

SCHEMA_VERSION = "ddc-v1"

class CustomerConfig(BaseModel):
    schema_version: Literal["ddc-v1"] = Field(default="ddc-v1")
    context: ProjectContext
    actors: List[Actor] = Field(..., min_length=1)
    entities: List[DomainEntity] = Field(..., min_length=1)
    relationships: List[Relationship] = Field(default_factory=list)
    business_rules: List[BusinessRule] = Field(default_factory=list)
    use_cases: List[UseCase] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_referential_integrity(self) -> "CustomerConfig":
        actor_ids = {a.id for a in self.actors}
        entity_ids = {e.id for e in self.entities}
        rule_ids = {r.id for r in self.business_rules}

        # Uniqueness
        if len({a.role_name for a in self.actors}) != len(self.actors):
            raise ValueError("Actor role_names must be unique.")
        if len({e.name for e in self.entities}) != len(self.entities):
            raise ValueError("Entity names must be unique.")

        # Entity ownership
        for ent in self.entities:
            if ent.owned_by_actor_id and ent.owned_by_actor_id not in actor_ids:
                raise ValueError(f"Entity {ent.name} owned_by unknown Actor: {ent.owned_by_actor_id}")
            if len({a.name for a in ent.attributes}) != len(ent.attributes):
                raise ValueError(f"Entity {ent.name} has duplicate attribute names.")

        # Relationships
        for rel in self.relationships:
            if rel.from_entity_id not in entity_ids:
                raise ValueError(f"Relationship {rel.name}: unknown from_entity_id {rel.from_entity_id}")
            if rel.to_entity_id not in entity_ids:
                raise ValueError(f"Relationship {rel.name}: unknown to_entity_id {rel.to_entity_id}")

        # Use cases
        for uc in self.use_cases:
            if uc.actor_id not in actor_ids:
                raise ValueError(f"UseCase {uc.name}: unknown actor_id {uc.actor_id}")
            if uc.primary_entity_id not in entity_ids:
                raise ValueError(f"UseCase {uc.name}: unknown primary_entity_id {uc.primary_entity_id}")
            for rid in uc.business_rule_ids:
                if rid not in rule_ids:
                    raise ValueError(f"UseCase {uc.name}: unknown business_rule_id {rid}")

        return self
```

### 2.5 Removed from old schema (with rationale)

| Field | Why removed |
|-------|-------------|
| `business_size`, `target_users`, `data_volume`, `access_scope`, `deadline_iso`, `must_have_features`, `nice_to_have_features`, `data_types`, `existing_data_uploads` | Conversational scaffolding that produced inconsistent agent inputs. Replaced by structured DDC. |
| `FeatureRequest` (top level) | Use cases supersede features. Each `UseCase.id` is the new "feature_id" for Phase-2 threading. |
| Free-form `business_context.description` | Replaced by `ProjectContext.domain_description`. |

### 2.6 Preserved from old schema

- `DataFieldType` enum (Phase 3) — reused as `Attribute.type`.
- `RelationshipKind` enum (Phase 3) — reused as `Relationship.kind`.
- `VisualStyle` enum — preserved on `ProjectContext`.

---

## 3. Pipeline-Wide Impact Map

### 3.1 RA's new role

The Requirements Analyst takes either:
- a **free-text intent** + minimal hints, and **expands** it into a complete DDC `CustomerConfig`; or
- a **partial DDC** from the structured intake form, and **completes** missing pieces (rules, relationships).

In both cases, RA may emit `RAOutput.needs_clarification=True` if it cannot disambiguate. Otherwise it returns a fully validated DDC. The `model_validator` provides automatic correctness feedback via the existing retry-on-ValidationError loop in `BaseAgent.execute`.

### 3.2 SA / Dev / QA consumption

| Agent | DDC inputs it must consume | Output it must produce |
|-------|----------------------------|------------------------|
| SA | Full DDC | `TechnicalDesign` keyed off `entity.id`, `use_case.id`, `actor.id` (no name lookups) |
| Dev | `TechnicalDesign` + DDC | `CodeOutput`, where each `FeatureImplementation.feature_id == use_case.id` |
| QA | DDC + `CodeOutput` | `QAReview`, where each `FeatureCoverage.feature_id == use_case.id` |

Phase-2 `feature_id` threading is preserved by **substituting `use_case.id` for the old `FeatureRequest.feature_id`**. No changes are needed to `CodeOutput.FeatureImplementation` or `QAReview.FeatureCoverage` schemas.

### 3.3 Frontend consumption

The intake form is rewritten in two modes:
- **Free-text mode** (default, easy): one textarea for `domain_description`, one for `industry`, plus a tiny set of toggles. RA expands into DDC.
- **Structured mode** (advanced, optional): explicit Actor / Entity / UseCase builders. Same zod schema as the backend.

Both modes produce the same `POST /api/pipeline/start` payload — a full DDC.

---

## 4. Phased Implementation (15 commits, all green)

> **Branch:** `feat/ddc-v1`. Open a PR after C7 for early CI signal; merge after C15.
>
> Each commit must leave `pytest backend/tests/` and `npm test` green. Implementation is gated by `settings.use_ddc` (default `False` until C14) so existing tests keep running.

### Backend foundation

**C1 — Add DDC schema alongside legacy.**
- `backend/app/schemas/customer_config_v2.py` — paste Section 2 above verbatim.
- Do **not** touch `customer_config.py` yet.
- `backend/app/config.py` — add `use_ddc: bool = False`.
- `backend/app/schemas/__init__.py` — re-export both as `CustomerConfig` (legacy) and `CustomerConfigV2`.
- **Test:** `tests/test_schemas_v2.py` with ≥10 cases — happy path, each integrity error, attribute uniqueness, role_name uniqueness, FK to missing entity, FK to missing actor, missing rule reference, schema_version literal, default values.
- **Commit msg:** `feat(schemas): add DDC v1 schema (CustomerConfigV2) behind use_ddc flag`

**C2 — Golden fixture.**
- `backend/tests/fixtures/ddc_ecommerce.json` — a complete, valid DDC for a small e-commerce store (Customer/Admin actors, Product/Order/OrderItem entities, 5 use cases, 3 rules). Reused by every later test.
- `backend/tests/conftest.py` — add `ddc_ecommerce` fixture loading this file.
- **Test:** `test_schemas_v2.py::test_golden_fixture_validates`
- **Commit msg:** `test(ddc): add e-commerce golden fixture`

### Agent prompt updates (gated by flag)

**C3 — RequirementsAnalyst DDC prompt.**
- `backend/app/agents/requirements_analyst.py` — add a `_build_user_prompt_ddc` method that targets DDC output; switch in `build_user_prompt` based on `settings.use_ddc`.
- The DDC prompt must include: the full `CustomerConfigV2` JSON schema (auto-generated via `CustomerConfigV2.model_json_schema()`), an example output (the e-commerce fixture), explicit instructions about ID generation (let Pydantic default factories do it; do not invent IDs), and clarification-question rules (max 5).
- `backend/app/schemas/ra_output.py` — add `RAOutputDDC` variant; selection in `_select_output_schema`.
- **Test:** `tests/test_requirements_analyst.py::TestDDC` — at least 6 cases mocking the LLM: returns valid DDC, returns clarification, returns invalid DDC and recovers on retry.
- **Commit msg:** `feat(ra): produce DDC v1 output when use_ddc=True`

**C4 — SolutionArchitect DDC prompt.**
- `backend/app/agents/solution_architect.py` — DDC branch in `build_user_prompt`. SA receives the full DDC and must output `TechnicalDesign` whose `data_models` enumerate every `DomainEntity`, whose `api_endpoints` enumerate every `UseCase`, and whose `ui_pages` group use cases by primary entity.
- The prompt must enforce: API path naming uses kebab-case derived from `use_case.name`; HTTP verb is GET for `query`, POST/PUT/DELETE for `command`; each endpoint includes `feature_id = use_case.id`.
- **Test:** `tests/test_solution_architect.py::TestDDC` — golden DDC in, validate that SA emits one endpoint per use case and one data model per entity.
- **Commit msg:** `feat(sa): consume DDC v1 and emit feature-id-threaded TechnicalDesign`

**C5 — Developer DDC prompt.**
- `backend/app/agents/developer.py` — DDC branch. Each `FeatureImplementation.feature_id` must equal the originating `UseCase.id`. Generated SQL DDL must respect `Attribute.type → DataFieldType` mapping (string→TEXT, integer→INTEGER, decimal→REAL, boolean→INTEGER 0/1, datetime→TEXT ISO, etc.) and `entity.states → CHECK constraint`.
- **Test:** `tests/test_developer.py::TestDDC` — verify `FeatureImplementation.feature_id` round-trips from DDC; verify generated `package.json` lists `better-sqlite3` and `next@14`.
- **Commit msg:** `feat(dev): generate code from DDC with use_case.id as feature_id`

**C6 — QAReviewer DDC prompt.**
- `backend/app/agents/qa_reviewer.py` — DDC branch. `FeatureCoverage.feature_id == use_case.id`. Verdict must include a per-rule check ("rule X enforced: yes/no/unclear").
- **Test:** `tests/test_qa_reviewer.py::TestDDC` — coverage list matches use case list 1:1; verdict `revise_code` when an entity attribute is missing from generated code.
- **Commit msg:** `feat(qa): assert DDC use cases and rules with use_case.id coverage`

### Pipeline integration

**C7 — Runner DDC pass-through.**
- `backend/app/pipeline/runner.py` — when `settings.use_ddc=True`, the runner threads `CustomerConfigV2` through context dicts as `customer_config_v2`. State machine and handler registry unchanged.
- `backend/app/api/routes.py` — `POST /start` accepts both shapes; field `schema_version` discriminates; legacy schema still works when `use_ddc=False`.
- **Test:** `tests/test_pipeline_runner.py::test_ddc_end_to_end` — full mocked run from DDC payload to `PIPELINE_COMPLETE`. `tests/test_api.py::test_start_accepts_ddc`.
- **Commit msg:** `feat(pipeline): thread CustomerConfigV2 through runner and API`

### Frontend foundation

**C8 — Zod mirror of DDC.**
- `frontend/lib/schemas/ddc.ts` — zod schema that exactly mirrors `CustomerConfigV2`. Same regex constraints, same min/max lengths, same enums.
- Regenerate types: `npm run gen:types` (backend must be running with `use_ddc=True`).
- **Test:** `frontend/__tests__/schemas/ddc.test.ts` — validate the same e-commerce golden fixture (loaded as JSON copy).
- **Commit msg:** `feat(fe/schemas): add DDC zod schema mirroring CustomerConfigV2`

**C9 — Free-text intake mode.**
- `frontend/components/intake-modal/sections/free-text.tsx` — single section with: project name (text), domain description (textarea, 50-1500 chars), industry (Select), visual_style (Select), mobile_first (toggle).
- The mapper produces a *minimal* DDC: single placeholder Actor (`Customer`, `anonymous`), single placeholder Entity (`Item` with one attribute `name`), single placeholder UseCase. RA expands.
- **Test:** `frontend/__tests__/mappers/free-text.test.ts` — minimal valid DDC produced.
- **Commit msg:** `feat(fe/intake): add free-text mode mapping to minimal DDC`

**C10 — Structured intake mode.**
- New components in `frontend/components/intake-modal/sections/`:
  - `actors.tsx` — list builder for `Actor` (role_name, auth_method, permissions).
  - `entities.tsx` — list builder for `DomainEntity` with nested `attributes` list builder.
  - `relationships.tsx` — list builder picking from/to entities by ID.
  - `rules.tsx` — list builder for `BusinessRule`.
  - `use-cases.tsx` — list builder; actor_id and primary_entity_id are dropdowns sourced from earlier sections.
- Mode toggle in `IntakeModal`: free-text vs structured. Persist mode choice in `localStorage`.
- **Test:** `frontend/__tests__/components/intake-structured.test.tsx` — render each builder; happy-path produces a valid zod object.
- **Commit msg:** `feat(fe/intake): add structured DDC builder mode`

**C11 — Mapper rewrite.**
- `frontend/lib/mappers/config.ts` — replace legacy `mapFormToCustomerConfig` with `mapFormToDDC` that takes the new union form schema and produces the DDC payload directly. No string concatenations, no hardcoded `auth_required`, no entity inference from `dataTypes`.
- Preserve a thin compatibility export for the old call sites (delete in C15).
- **Test:** `frontend/__tests__/mappers/config.test.ts` — rewrite all 19 cases against DDC.
- **Commit msg:** `refactor(fe/mappers): produce DDC payload directly`

### Cutover

**C12 — Documentation refresh.**
- Update CLAUDE.md §"Intake Form — Pending Refactor" to reference the DDC migration; add a §"DDC Schema" describing the contract; update §"Pipeline Data Flow" to show DDC flowing through.
- Update `docs/Aegis_Research_Decisions_Plan.md` §4.4 if present.
- **Commit msg:** `docs: document DDC v1 schema and intake modes`

**C13 — Wire benchmark to DDC.**
- `evaluation/run_benchmark.py` — accept DDC payloads; update result scoring to check `use_case.id` coverage in the QAReview output.
- Add `evaluation/fixtures/ddc_ecommerce.json` (copy of backend golden) and one more (`ddc_taskmgr.json`) for diversity.
- **Test:** dry-run `python evaluation/run_benchmark.py --dry` against a mocked backend.
- **Commit msg:** `feat(eval): support DDC payloads in benchmark harness`

**C14 — Flip default flag.**
- `backend/app/config.py` — `use_ddc: bool = True`.
- Run full backend suite + frontend suite + one full e2e benchmark run. All must pass.
- **Commit msg:** `feat(ddc): enable DDC v1 by default`

**C15 — Delete legacy.**
- Delete `backend/app/schemas/customer_config.py` (legacy file).
- Rename `customer_config_v2.py` → `customer_config.py`. Update imports.
- Delete legacy intake sections (`business-context`, `data-content`, `features`, `problem-statement`, `technical`, `timeline`); keep only `free-text` and the structured DDC sections.
- Delete `settings.use_ddc` flag and all branches keyed on it.
- Delete legacy fixture files in `conftest.py` (`valid_customer_config`, `valid_finalized_config`).
- Run full suite; all must pass.
- **Commit msg:** `chore(ddc): remove legacy schema and feature flag`

---

## 5. Failure Modes and Contingencies

| If this happens during implementation… | …do this |
|----------------------------------------|----------|
| RA produces DDC with referential integrity error | The existing `BaseAgent` retry-on-ValidationError loop catches it and re-prompts once with the error appended. If still failing, RA emits `needs_clarification=True` with a question about the missing reference. **No new code needed.** |
| LLM invents IDs (e.g. `act_xxx`) instead of letting Pydantic generate them | Add an explicit prompt rule: "Do NOT include `id` fields in your output; Pydantic will generate them." Validate via a custom `model_validator` that strips client-supplied IDs in RA-only mode. |
| SA emits API endpoints not corresponding to use cases | QA catches the missing `feature_id` in `FeatureCoverage`. Verdict `revise_design` triggers `DESIGN_REVISION` (existing flow). |
| Dev's generated SQL uses wrong types | Build check (`pipeline/build_checker.py`) currently does `node --check` only. Add a lightweight DDL validator: parse `CREATE TABLE` statements and confirm column types map to `DataFieldType`. Defer if non-blocking. |
| Token bloat — the DDC JSON inflates the prompt and breaks `max_tokens=8192` | The 1500-char cap on `domain_description` and 500-char caps on rule fields keep payloads bounded. If still exceeding, drop `description` fields from prompts (keep them in storage). Monitor via existing token-usage events. |
| Frontend zod and backend Pydantic drift | Re-run `npm run gen:types` after every schema change; CI step (Section 6) blocks merge on drift. |
| Existing test suite breaks during partial migration (commits C3–C13) | Every commit is gated by `use_ddc=False` default. Legacy tests run on legacy path; DDC tests run on DDC path. The flip happens once, in C14. |
| User submits malformed DDC via the structured form | Zod validates before submit; backend Pydantic re-validates on receipt; specific error messages bubble to the form. |
| Free-text mode produces a minimal DDC that RA can't expand into something useful | RA's clarification loop (max 3 rounds) gathers missing pieces; if still incomplete, the `model_validator` rejects, and the pipeline transitions to `FAILED` with a clear error. |
| Weaker implementation model picks the wrong file paths | All paths above are absolute and explicit; the golden fixture (C2) is the comparison artifact. If a commit's tests pass, the commit is correct. |
| `node --check` ESM/CJS issue blocks build_check on generated code | Already handled by Phase 4 BUILD_CHECK with the `enable_full_build_check` opt-in. No change. |
| The flag flip in C14 breaks integration tests that hardcode legacy schema shapes | Grep for `business_size`, `data_types`, `must_have_features`, `target_users` before C14; rewrite or delete; this is part of C14's verification. |

---

## 6. CI / Verification Steps

After each commit:

```bash
# Backend
cd backend && source venv/bin/activate
pytest tests/ -x

# Frontend
cd ../frontend
npm test
npm run lint
npm run build

# Schema drift (after backend schema or route changes)
cd ../frontend
npm run gen:types
git diff --exit-code lib/utils/generated/schema.d.ts  # must be clean
```

End-to-end smoke (after C7 and C14):

```bash
# Terminal 1
cd backend && uvicorn app.main:app --port 8000

# Terminal 2
cd evaluation
python run_benchmark.py --fixture fixtures/ddc_ecommerce.json
# Expect: PIPELINE_COMPLETE, all use_case.ids present in QAReview.feature_coverage
```

---

## 7. Critical Files (modified or created)

### Created
- `backend/app/schemas/customer_config_v2.py` (C1, renamed in C15)
- `backend/tests/fixtures/ddc_ecommerce.json` (C2)
- `backend/tests/test_schemas_v2.py` (C1)
- `evaluation/fixtures/ddc_ecommerce.json` (C13)
- `evaluation/fixtures/ddc_taskmgr.json` (C13)
- `frontend/lib/schemas/ddc.ts` (C8)
- `frontend/components/intake-modal/sections/free-text.tsx` (C9)
- `frontend/components/intake-modal/sections/actors.tsx` (C10)
- `frontend/components/intake-modal/sections/entities.tsx` (C10)
- `frontend/components/intake-modal/sections/relationships.tsx` (C10)
- `frontend/components/intake-modal/sections/rules.tsx` (C10)
- `frontend/components/intake-modal/sections/use-cases.tsx` (C10)

### Modified
- `backend/app/config.py` — flag (C1, removed C15)
- `backend/app/schemas/__init__.py` — exports (C1, C15)
- `backend/app/schemas/ra_output.py` — DDC variant (C3)
- `backend/app/agents/requirements_analyst.py` (C3)
- `backend/app/agents/solution_architect.py` (C4)
- `backend/app/agents/developer.py` (C5)
- `backend/app/agents/qa_reviewer.py` (C6)
- `backend/app/pipeline/runner.py` (C7)
- `backend/app/api/routes.py` (C7)
- `backend/tests/conftest.py` — fixture loader (C2), legacy cleanup (C15)
- `frontend/lib/mappers/config.ts` (C11)
- `frontend/components/intake-modal/index.tsx` — mode toggle (C10)
- `frontend/__tests__/mappers/config.test.ts` (C11)
- `evaluation/run_benchmark.py` (C13)
- `CLAUDE.md` (C12)

### Deleted (C15)
- `backend/app/schemas/customer_config.py` (legacy)
- `frontend/components/intake-modal/sections/business-context.tsx`
- `frontend/components/intake-modal/sections/data-content.tsx`
- `frontend/components/intake-modal/sections/features.tsx`
- `frontend/components/intake-modal/sections/problem-statement.tsx`
- `frontend/components/intake-modal/sections/technical.tsx`
- `frontend/components/intake-modal/sections/timeline.tsx`

---

## 8. Implementation Notes for the Executing Model

- **Do not skip the flag.** The whole reason for `use_ddc` is to keep CI green at every step. If you find yourself needing to delete a legacy file before C15, the gating is wrong.
- **Generate the schema's JSON Schema dynamically** via `CustomerConfigV2.model_json_schema()` — do not hand-write it; it drifts.
- **Schema goes in the SYSTEM prompt, not the USER prompt.** `BaseAgent` already wires `cache_control` on system prompts (see `app/agents/base.py`). The DDC JSON schema is large (~3-5k tokens) and stable across calls; placing it in the system prompt means it is cached once per agent and reused on every retry / revision cycle. Pre-compute the schema string at module load (e.g. `_DDC_SCHEMA_JSON = json.dumps(CustomerConfigV2.model_json_schema(), indent=2)`) and inject into the system prompt template. The golden fixture (C2) goes in the system prompt for the same reason.
- **The golden fixture is the spec.** When in doubt about what a valid DDC looks like, read `backend/tests/fixtures/ddc_ecommerce.json`.
- **`use_case.id` is the new `feature_id`.** Do not invent a new threading scheme.
- **Pydantic IDs are auto-generated.** Tell the LLM in the prompt: "Do NOT output `id` fields; the server generates them." If the LLM emits IDs anyway, Pydantic accepts them — but a stricter `model_validator` could strip client-supplied IDs in RA mode if drift becomes a problem.
- **Tests-first preferred** for schemas (C1, C2, C8). For agents (C3-C6), write the prompt first (mocking the LLM in tests) since the prompt is the spec.
- **Mode toggle in IntakeModal (C10).** Persist the user's mode choice in `localStorage` so refresh keeps them in their chosen flow. Default is free-text.
