# Plan: Wire BUILD_CHECK result into QA Reviewer context

**Written against:** `main` @ 46c1730
**Goal:** Pass the `BuildCheckResult` from the pipeline `BUILD_CHECK` stage into the QA Reviewer so it can cite specific build errors in its review and refuse to approve when build errors exist.

---

## Background (read this before starting)

### Pipeline flow

```
CodeOutput → BUILD_CHECK → REVIEW → approve/revise_code/revise_design
```

### The gap

`backend/app/pipeline/runner.py` — `_run_build_check()` (line 284) saves the result into the runner's shared context:

```python
result = await run_build_check(code_output, run_id=self.current_run.run_id)
self.context["build_check_result"] = result   # line 296
```

But `_run_review()` (line 331) builds `qa_context` WITHOUT it:

```python
qa_context = {
    "customer_config_v2": self.context["customer_config_v2"],
    "technical_design": self.context["technical_design"],
    "code_output": self.context["code_output"],
    # build_check_result is MISSING here
}
result = await qa.execute(qa_context, ...)
```

For comparison, the Developer's code-revision context (line 396) DOES include it via `self.context.get("build_check_result")`.

`backend/app/agents/qa_reviewer.py` — `_build_user_prompt_ddc()` (line 147) only consumes `customer_config_v2`, `technical_design`, `code_output`. It does not look for `build_check_result` at all.

### `BuildCheckResult` schema (from `backend/app/schemas/agent_outputs.py`)

```python
class BuildCheckResult(BaseModel):
    passed: bool
    duration_ms: int
    files_checked: int
    issues: list[BuildCheckIssue]
    full_build_attempted: bool
    full_build_log: str | None = None

class BuildCheckIssue(BaseModel):
    file: str
    line: int | None = None
    column: int | None = None
    severity: str   # "error" | "warning"
    message: str
    check: str      # e.g. "syntax_js", "json_parse", "next_build", "dep_drift"
```

### What this fix does

1. Adds `"build_check_result"` to `qa_context` in `_run_review()` using `self.context.get(...)` (graceful when absent).
2. Updates `_build_user_prompt_ddc()` to read `build_check_result` from context and append a `BUILD CHECK RESULT` section. If failed, the JSON includes the issues list. If passed, a brief confirmation. If `None`, the section is omitted.
3. Adds one sentence to the QA Reviewer system prompt's MANDATORY DDC REVIEW STEPS instructing QA to incorporate any build check errors into its issues list and to refuse `approve` when build errors are present.

### Compatibility notes

- `QAReview` schema is unchanged. Build check is additional input context only.
- `context.get("build_check_result")` (not `[...]`) means `None` is acceptable — covers `enable_full_build_check=False` and any test that doesn't set it up.
- Existing test `test_ddc_qa_receives_customer_config_v2_technical_design_and_code_output` in `test_pipeline_runner.py` (line 399) just asserts these keys are *in* the context. It does not assert exclusivity, so adding `build_check_result` will not break it.
- Existing QA tests build their own context dicts and call `agent.build_user_prompt({...})` / `agent.execute({...})` directly — none of them read `build_check_result`, so omitting the key keeps them passing.

### Test infrastructure already in place

- `backend/tests/test_pipeline_runner.py` has an autouse fixture `mock_build_check_pass` (lines 43–48) that patches `app.pipeline.runner.run_build_check` to return a `BuildCheckResult(passed=True, duration_ms=5, files_checked=3)`. New runner tests pick this up automatically.
- `backend/tests/test_qa_reviewer.py` uses fixtures `mock_anthropic`, `captured_events`, `ddc_ecommerce`, `sample_run_id` from `conftest.py`.
- Neither test file uses FastAPI; neither needs the `mock_db` autouse fixture.

---

### Task 1: Failing tests (TDD red)

**Files:**
- Modify: `backend/tests/test_qa_reviewer.py`
- Modify: `backend/tests/test_pipeline_runner.py`

- [ ] **Step 1: Add `BuildCheckResult` and `BuildCheckIssue` to imports in `test_qa_reviewer.py`.**

Open `backend/tests/test_qa_reviewer.py` and update the import block (lines 21–33). The current block imports from `app.schemas.agent_outputs`. Replace it with:

```python
from app.schemas.agent_outputs import (
    QAReview,
    ReviewVerdict,
    TechnicalDesign,
    APIEndpoint,
    DataModel,
    DataField,
    UIComponent,
    FileSpec,
    CodeOutput,
    CodeFile,
    FeatureImplementation,
    BuildCheckResult,
    BuildCheckIssue,
)
```

- [ ] **Step 2: Add a failing test asserting the QA prompt includes the build check section when present.**

Append the following test method to `class TestDDCQASync` in `backend/tests/test_qa_reviewer.py` (place it immediately after `test_ddc_user_prompt_not_legacy_format`):

```python
    def test_ddc_user_prompt_includes_build_check_when_present(
        self, ddc_ecommerce: CustomerConfigV2
    ):
        agent = self._make_agent()
        design = _make_technical_design_from_ddc(ddc_ecommerce)
        code = _make_code_output(ddc_ecommerce)
        build_check = BuildCheckResult(
            passed=False,
            duration_ms=42,
            files_checked=5,
            issues=[
                BuildCheckIssue(
                    file="app/api/orders/route.js",
                    line=12,
                    column=3,
                    severity="error",
                    message="Unexpected token '}'",
                    check="syntax_js",
                )
            ],
            full_build_attempted=True,
            full_build_log=None,
        )
        prompt = agent.build_user_prompt({
            "customer_config_v2": ddc_ecommerce,
            "technical_design": design,
            "code_output": code,
            "build_check_result": build_check,
        })
        assert "BUILD CHECK RESULT" in prompt
        assert "syntax_js" in prompt
        assert "app/api/orders/route.js" in prompt

    def test_ddc_user_prompt_omits_build_check_when_absent(
        self, ddc_ecommerce: CustomerConfigV2
    ):
        agent = self._make_agent()
        design = _make_technical_design_from_ddc(ddc_ecommerce)
        code = _make_code_output(ddc_ecommerce)
        prompt = agent.build_user_prompt({
            "customer_config_v2": ddc_ecommerce,
            "technical_design": design,
            "code_output": code,
        })
        assert "BUILD CHECK RESULT" not in prompt
```

- [ ] **Step 3: Add a failing runner test asserting `build_check_result` is in the QA context.**

Append the following test method to `class TestDDCPipeline` in `backend/tests/test_pipeline_runner.py` (place it immediately after `test_ddc_qa_receives_customer_config_v2_technical_design_and_code_output`):

```python
    async def test_ddc_qa_receives_build_check_result(self, ddc_ecommerce):
        events: list[PipelineEvent] = []
        agents = _agents_for_ddc_happy_path(ddc_ecommerce)
        runner = self._make_runner(agents, events)
        await runner.run(ddc_ecommerce)
        qa_context = agents["qa_reviewer"].execute.call_args[0][0]
        assert "build_check_result" in qa_context
        assert qa_context["build_check_result"] is not None
        assert qa_context["build_check_result"].passed is True
```

The autouse `mock_build_check_pass` fixture already places a passing `BuildCheckResult` in `runner.context["build_check_result"]` because `_run_build_check` runs before `_run_review`.

- [ ] **Step 4: Run the new tests and verify they fail.**

Command (from `backend/`):

```bash
pytest tests/test_qa_reviewer.py::TestDDCQASync::test_ddc_user_prompt_includes_build_check_when_present tests/test_qa_reviewer.py::TestDDCQASync::test_ddc_user_prompt_omits_build_check_when_absent tests/test_pipeline_runner.py::TestDDCPipeline::test_ddc_qa_receives_build_check_result -v
```

Expected failures:
- `test_ddc_user_prompt_includes_build_check_when_present` — `AssertionError: assert 'BUILD CHECK RESULT' in prompt` (the prompt builder ignores the key).
- `test_ddc_user_prompt_omits_build_check_when_absent` — passes by accident (the key is already not added). That's fine; it's a guard for the next step's edge case.
- `test_ddc_qa_receives_build_check_result` — `AssertionError: assert 'build_check_result' in qa_context` (runner doesn't pass it through).

- [ ] **Step 5: Commit the failing tests.**

```bash
git add backend/tests/test_qa_reviewer.py backend/tests/test_pipeline_runner.py
git commit -m "test(qa): add failing tests for build_check_result in QA context"
```

---

### Task 2: Implementation — `runner.py`

**Files:**
- Modify: `backend/app/pipeline/runner.py`

- [ ] **Step 1: Update `_run_review()` to pass `build_check_result` into the QA context.**

Replace the existing `_run_review()` method (lines 331–376) with:

```python
    async def _run_review(self) -> PipelineState:
        """Run the QA Reviewer agent."""
        qa = self.agents["qa_reviewer"]

        qa_context = {
            "customer_config_v2": self.context["customer_config_v2"],
            "technical_design": self.context["technical_design"],
            "code_output": self.context["code_output"],
            "build_check_result": self.context.get("build_check_result"),
        }

        result = await qa.execute(
            qa_context, self.current_run.run_id, self.emit_event
        )

        self.context["qa_review"] = result

        verdict = result.verdict.value

        if verdict == "approve":
            return PipelineState.COMPLETE

        if verdict == "revise_code":
            if self.code_revision_count >= settings.max_code_revision_cycles:
                logger.info(
                    "Code revision cap reached (%d). Accepting current output.",
                    settings.max_code_revision_cycles,
                )
                self.current_run.outcome = "partial"
                return PipelineState.COMPLETE
            return PipelineState.CODE_REVISION

        if verdict == "revise_design":
            if self.design_revision_count >= settings.max_design_revision_cycles:
                logger.info(
                    "Design revision cap reached (%d). Falling back to code revision.",
                    settings.max_design_revision_cycles,
                )
                if self.code_revision_count < settings.max_code_revision_cycles:
                    return PipelineState.CODE_REVISION
                self.current_run.outcome = "partial"
                return PipelineState.COMPLETE
            return PipelineState.DESIGN_REVISION

        # Unknown verdict — treat as approved
        logger.warning("Unknown QA verdict: %s. Treating as approved.", verdict)
        return PipelineState.COMPLETE
```

The only change is the new `"build_check_result": self.context.get("build_check_result"),` line in `qa_context`.

- [ ] **Step 2: Run the runner test and verify it passes.**

Command (from `backend/`):

```bash
pytest tests/test_pipeline_runner.py::TestDDCPipeline::test_ddc_qa_receives_build_check_result -v
```

Expected: `1 passed`.

- [ ] **Step 3: Run the entire pipeline-runner suite to confirm no regressions.**

```bash
pytest tests/test_pipeline_runner.py -v
```

Expected: all tests pass (the previously passing tests remain green; the new test now passes).

- [ ] **Step 4: Commit the runner change.**

```bash
git add backend/app/pipeline/runner.py
git commit -m "feat(runner): pass build_check_result into QA Reviewer context"
```

---

### Task 3: Implementation — `qa_reviewer.py`

**Files:**
- Modify: `backend/app/agents/qa_reviewer.py`

- [ ] **Step 1: Update the system prompt to mention the build check.**

In `backend/app/agents/qa_reviewer.py`, locate Step 5 of `MANDATORY DDC REVIEW STEPS` (lines 72–75):

```
Step 5 — CODE QUALITY
- Syntactic validity, no placeholder stubs, proper imports, error handling
- No hardcoded secrets, no SQL injection vectors
- "use client" only where interactivity is needed
```

Replace it with a Step 5 that includes a build-check sub-step, and renumber subsequent steps. The full updated `MANDATORY DDC REVIEW STEPS` section (replace lines 44–91) becomes:

```
MANDATORY DDC REVIEW STEPS

Step 1 — USE CASE COVERAGE (requirements_coverage)
For every UseCase in the DDC, produce one FeatureCoverage entry:
  - feature_id = use_case.id (EXACTLY — do not use use_case.name)
  - implemented = true if the CodeOutput contains working code for this use case
  - evidence = brief note (which file, which endpoint)
The requirements_coverage list MUST have exactly one entry per use_case, no more, no fewer.

Step 2 — ENTITY ATTRIBUTE CHECK
For every DomainEntity, verify that the generated code (schema.sql or db.js) defines a table with:
  - A column for every Attribute listed in the DDC entity
  - Correct SQL types (DDC decimal → REAL, DDC boolean → INTEGER, DDC datetime → TEXT, etc.)
  - A CHECK constraint for entities with multiple states, e.g.: CHECK (state IN ('Pending','Confirmed'))
If any attribute is missing from the generated code, create a "critical" or "major" issue and set verdict to "revise_code".

Step 3 — BUSINESS RULE ENFORCEMENT CHECK
For every BusinessRule in the DDC, determine whether the generated code enforces it.
In your reasoning, include a per-rule check for EVERY rule using this format:
  "Rule '<rule.description>': enforced=yes|no|unclear — <brief explanation>"
If a rule is not enforced (enforced=no), create a "major" issue with a specific actionable suggestion.
If enforcement is unclear (enforced=unclear), create a "minor" issue.

Step 4 — DESIGN COMPLIANCE
- Every TechnicalDesign.api_endpoints entry should be implemented
- feature_id on each endpoint must match a use_case.id in the DDC
- Every TechnicalDesign.data_models entry must appear in the code

Step 5 — CODE QUALITY
- Syntactic validity, no placeholder stubs, proper imports, error handling
- No hardcoded secrets, no SQL injection vectors
- "use client" only where interactivity is needed

Step 6 — BUILD CHECK INCORPORATION
If a BUILD CHECK RESULT section is present in the input, treat its issues as authoritative evidence about the code's correctness. For every build issue with severity "error", create a corresponding entry in your `issues` list (severity "critical" if it prevents the app from building, otherwise "major") that cites the file and the build check's `check` name. If the build check did not pass (`passed: false` or any error-severity issue), the verdict MUST be at least "revise_code" — you cannot return "approve" while build errors exist.

Step 7 — VERDICT AND SCORE
Score 1-5 (see criteria below). Verdict rules:
- All use cases covered + all critical rules enforced + build check passed + score >= 3 → "approve"
- Any use case missing OR any critical rule not enforced OR build check failed OR score < 3 → "revise_code"
- Missing data models or fundamentally wrong API structure → "revise_design" (rare)

Score criteria:
- 5: Complete, clean, all rules enforced, no issues.
- 4: Good. Minor issues only.
- 3: Acceptable. All use cases work, minor rule gaps.
- 2: Missing use cases or unenfored critical rules.
- 1: Major features missing or broken code.

Step 8 — SUMMARY
Write in plain business language for the customer. Mention which capabilities work, which don't, and what will be fixed.
```

- [ ] **Step 2: Update `_build_user_prompt_ddc()` to append the build check section.**

Replace the current `_build_user_prompt_ddc()` method (lines 147–168) with:

```python
    def _build_user_prompt_ddc(self, context: dict[str, Any]) -> str:
        """Build user prompt for DDC mode."""
        ddc = context["customer_config_v2"]
        technical_design = context["technical_design"]
        code_output = context["code_output"]
        build_check_result = context.get("build_check_result")

        ddc_json = json.dumps(
            ddc.model_dump(mode="json") if hasattr(ddc, "model_dump") else ddc,
            indent=2,
        )
        design_json = json.dumps(technical_design.model_dump(mode="json"), indent=2)
        code_json = json.dumps(code_output.model_dump(mode="json"), indent=2)

        prompt = (
            f"REVIEW THE IMPLEMENTATION\n\n"
            f"Apply all mandatory DDC review steps. "
            f"requirements_coverage must have one entry per use_case keyed by use_case.id. "
            f"reasoning must include a per-rule enforcement check for every BusinessRule.\n\n"
            f"DDC INPUT:\n{ddc_json}\n\n"
            f"TECHNICAL DESIGN:\n{design_json}\n\n"
            f"CODE IMPLEMENTATION:\n{code_json}"
        )

        if build_check_result is not None:
            bc_json = json.dumps(
                build_check_result.model_dump(mode="json"),
                indent=2,
            )
            header = (
                "BUILD CHECK RESULT (FAILED — review these issues):"
                if not build_check_result.passed
                else "BUILD CHECK RESULT (passed):"
            )
            prompt += f"\n\n{header}\n{bc_json}"

        return prompt
```

- [ ] **Step 3: Run the QA reviewer tests and verify the new ones pass.**

Command (from `backend/`):

```bash
pytest tests/test_qa_reviewer.py -v
```

Expected: all tests pass, including the two new ones (`test_ddc_user_prompt_includes_build_check_when_present`, `test_ddc_user_prompt_omits_build_check_when_absent`).

- [ ] **Step 4: Commit the QA Reviewer changes.**

```bash
git add backend/app/agents/qa_reviewer.py
git commit -m "feat(qa): consume build_check_result in DDC prompt and require revise_code on build errors"
```

---

### Task 4: Regression — full backend test suite

**Files:** none (verification only)

- [ ] **Step 1: Run the full backend test suite.**

Command (from `backend/`):

```bash
pytest tests/ -v
```

Expected: all 270 previously-passing tests still pass; the 3 newly-added tests (2 in `test_qa_reviewer.py`, 1 in `test_pipeline_runner.py`) pass. Total: 273 passed, 0 failed.

- [ ] **Step 2: If any unrelated test fails, investigate and fix before proceeding.**

The most likely failure surface is anywhere a test constructs a QA context dict by hand and asserts on the returned prompt's exact length or content. Grep for likely callers:

```bash
grep -rn "build_user_prompt" backend/tests/
grep -rn "qa_reviewer" backend/tests/
```

If a test asserts the prompt does NOT contain something that's now appended, update the assertion. Do not weaken assertions that were checking real behavior; only relax assertions that were incidentally tied to the old prompt length.

---

### Task 5: STATUS.md — mark item #4 complete

**Files:**
- Modify: `STATUS.md`

- [ ] **Step 1: Update the priority list row.**

In `STATUS.md`, find this line in the priority table:

```
| 4 | Wire `BUILD_CHECK` result into QA Reviewer context | `runner.py`, `qa_reviewer.py` | ☐ |
```

Replace it with:

```
| 4 | Wire `BUILD_CHECK` result into QA Reviewer context | `runner.py`, `qa_reviewer.py` | ✓ |
```

- [ ] **Step 2: Commit the STATUS update.**

```bash
git add STATUS.md
git commit -m "chore(status): mark BUILD_CHECK→QA wiring complete"
```

- [ ] **Step 3: Final verification — confirm all tests still pass.**

```bash
pytest tests/ -q
```

Expected: `273 passed` (or whatever the new total is — three more than the prior baseline of 270).
