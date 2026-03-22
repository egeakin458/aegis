---
name: conftest_and_fixtures
description: Existing fixtures in tests/conftest.py and their shapes — use these rather than redefining
type: project
---

Fixtures in `/home/ege/projects/aegis/backend/tests/conftest.py`:

- `valid_customer_config` — CustomerConfig with Cafe Latte business, food_and_beverage, SMALL size, 2 features
- `valid_finalized_config(valid_customer_config)` — FinalizedConfig wrapping the above, is_complete=True
- `sample_clarification_question` — ClarificationQuestion id="q1", topic="authentication"
- `sample_clarification_round(sample_clarification_question)` — ClarificationRound round_number=1, answers={"q1": "Yes, always"}
- `sample_run_id` — str "test-run-00000000-0000-0000-0000-000000000001"
- `captured_events` — returns (list[PipelineEvent], emit_callback); pass callback as emit_event, inspect list after
- `mock_anthropic(monkeypatch)` — patches app.agents.base.anthropic.AsyncAnthropic; returns mock client. Set mock_client.messages.create = AsyncMock(return_value=...) per test
- `make_mock_response` — exposes _make_mock_response(json_payload: dict|str) helper

The `_make_mock_response` helper sets usage.input_tokens=100, output_tokens=200 by default.

## Async fixture pattern (pytest-asyncio 1.3.0, strict mode)

pytest-asyncio 1.3.0 is installed with default `asyncio_mode = "strict"`. In strict mode:
- Async test functions need `@pytest.mark.asyncio`.
- Async fixtures MUST use `@pytest_asyncio.fixture` (not plain `@pytest.fixture`) to be handled correctly.
  Plain `@pytest.fixture` on an async function is silently ignored in strict mode.
- Import: `import pytest_asyncio` then `@pytest_asyncio.fixture(autouse=True)` etc.

## DB test pattern (test_database.py)

Each test uses `@pytest_asyncio.fixture(autouse=True)` named `setup_db` that calls:
  `await init_db(":memory:")` before, `await close_db()` after.
This gives each test a fresh in-memory SQLite database with no shared state.

`_connection` is module-level in `app/db/database.py`. `close_db()` sets it to None;
`init_db(":memory:")` creates a new one. Tests that call `close_db()` mid-test must
call `init_db(":memory:")` again before using repository functions.

## Output storage test pattern (test_output_storage.py)

`@pytest.fixture(autouse=True)` named `use_tmp_dir` patches:
  `app.pipeline.output_storage.settings.output_dir` → `str(tmp_path)`
The module does `Path(settings.output_dir) / run_id`, so the string form is correct.
`save_output` is async — all tests use `@pytest.mark.asyncio` and `async def`.
