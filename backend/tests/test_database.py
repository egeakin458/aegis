"""
Tests for app/db/database.py and app/db/repositories.py.

Coverage:
  1. init_db — creates pipeline_runs and pipeline_events tables
  2. get_connection — raises RuntimeError when DB not initialized
  3. close_db — sets connection to None (get_connection raises afterwards)
  4. save_run + get_run roundtrip — all fields persisted and retrieved
  5. update_run — state, completed_at, outcome, tokens, cycles reflected
  6. get_run — returns None for unknown run_id
  7. save_event + get_events roundtrip — all fields persisted and retrieved
  8. get_events ordering — events returned ordered by timestamp ascending
  9. get_events — returns empty list for unknown run_id
 10. get_events — multiple events for same run_id all retrieved
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
import pytest_asyncio

from app.db.database import close_db, get_connection, init_db
from app.db.repositories import get_events, get_run, save_event, save_run, update_run
from app.schemas.customer_config import CustomerConfigV2
from app.schemas.pipeline_events import (
    AgentName,
    EventType,
    PipelineEvent,
    PipelineRun,
    PipelineState,
    TokenUsage,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Initialize an in-memory DB before each test, tear it down after."""
    await init_db(":memory:")
    yield
    await close_db()


@pytest.fixture
def minimal_customer_config(ddc_ecommerce) -> CustomerConfigV2:
    """Minimal valid CustomerConfigV2 (DDC) for repository tests."""
    return ddc_ecommerce


@pytest.fixture
def minimal_pipeline_run() -> PipelineRun:
    """Minimal valid PipelineRun for repository tests."""
    return PipelineRun(
        run_id="run-00000000-0000-0000-0000-000000000001",
        state=PipelineState.INTAKE,
    )


@pytest.fixture
def minimal_event(minimal_pipeline_run: PipelineRun) -> PipelineEvent:
    """Minimal valid PipelineEvent for repository tests."""
    return PipelineEvent(
        event_id="evt-00000000-0000-0000-0000-000000000001",
        run_id=minimal_pipeline_run.run_id,
        agent=AgentName.SYSTEM,
        event_type=EventType.PIPELINE_STARTED,
        message="Pipeline started",
    )


# ---------------------------------------------------------------------------
# 1. init_db — table creation
# ---------------------------------------------------------------------------


class TestInitDb:
    @pytest.mark.asyncio
    async def test_init_db_creates_pipeline_runs_table(self):
        conn = await get_connection()
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='pipeline_runs'"
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row["name"] == "pipeline_runs"

    @pytest.mark.asyncio
    async def test_init_db_creates_pipeline_events_table(self):
        conn = await get_connection()
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='pipeline_events'"
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row["name"] == "pipeline_events"

    @pytest.mark.asyncio
    async def test_init_db_creates_events_run_id_index(self):
        conn = await get_connection()
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_events_run_id'"
        )
        row = await cursor.fetchone()
        assert row is not None

    @pytest.mark.asyncio
    async def test_init_db_with_memory_path_returns_connection(self):
        # setup_db already calls init_db(":memory:"), so connection must be live
        conn = await get_connection()
        assert conn is not None

    @pytest.mark.asyncio
    async def test_init_db_is_idempotent_for_create_if_not_exists(self):
        # Calling init_db a second time on same path should not raise
        await close_db()
        await init_db(":memory:")
        conn = await get_connection()
        assert conn is not None


# ---------------------------------------------------------------------------
# 2. get_connection — runtime error when not initialized
# ---------------------------------------------------------------------------


class TestGetConnection:
    @pytest.mark.asyncio
    async def test_get_connection_raises_when_db_not_initialized(self):
        # Close the connection set up by autouse fixture
        await close_db()
        with pytest.raises(RuntimeError, match="Database not initialized"):
            await get_connection()

    @pytest.mark.asyncio
    async def test_get_connection_returns_connection_after_init(self):
        conn = await get_connection()
        assert conn is not None


# ---------------------------------------------------------------------------
# 3. close_db — sets connection to None
# ---------------------------------------------------------------------------


class TestCloseDb:
    @pytest.mark.asyncio
    async def test_close_db_causes_get_connection_to_raise(self):
        await close_db()
        with pytest.raises(RuntimeError, match="Database not initialized"):
            await get_connection()

    @pytest.mark.asyncio
    async def test_close_db_is_idempotent(self):
        await close_db()
        # Calling close_db again on an already-None connection must not raise
        await close_db()

    @pytest.mark.asyncio
    async def test_close_db_allows_reinit(self):
        await close_db()
        await init_db(":memory:")
        conn = await get_connection()
        assert conn is not None


# ---------------------------------------------------------------------------
# 4. save_run + get_run roundtrip
# ---------------------------------------------------------------------------


class TestSaveRunAndGetRun:
    @pytest.mark.asyncio
    async def test_save_and_get_run_returns_matching_run_id(
        self, minimal_pipeline_run, minimal_customer_config
    ):
        await save_run(minimal_pipeline_run, minimal_customer_config)
        row = await get_run(minimal_pipeline_run.run_id)
        assert row is not None
        assert row["run_id"] == minimal_pipeline_run.run_id

    @pytest.mark.asyncio
    async def test_save_run_persists_state(
        self, minimal_pipeline_run, minimal_customer_config
    ):
        await save_run(minimal_pipeline_run, minimal_customer_config)
        row = await get_run(minimal_pipeline_run.run_id)
        assert row["state"] == PipelineState.INTAKE.value

    @pytest.mark.asyncio
    async def test_save_run_persists_started_at(
        self, minimal_pipeline_run, minimal_customer_config
    ):
        await save_run(minimal_pipeline_run, minimal_customer_config)
        row = await get_run(minimal_pipeline_run.run_id)
        assert row["started_at"] is not None
        # Should be parseable as an ISO-8601 datetime
        parsed = datetime.fromisoformat(row["started_at"])
        assert parsed is not None

    @pytest.mark.asyncio
    async def test_save_run_persists_customer_config_as_json(
        self, minimal_pipeline_run, minimal_customer_config
    ):
        await save_run(minimal_pipeline_run, minimal_customer_config)
        row = await get_run(minimal_pipeline_run.run_id)
        config_data = json.loads(row["customer_config_json"])
        assert config_data["schema_version"] == "ddc-v1"
        assert "context" in config_data

    @pytest.mark.asyncio
    async def test_save_run_persists_total_tokens(
        self, minimal_pipeline_run, minimal_customer_config
    ):
        minimal_pipeline_run.total_tokens = TokenUsage(
            input_tokens=42, output_tokens=99
        )
        await save_run(minimal_pipeline_run, minimal_customer_config)
        row = await get_run(minimal_pipeline_run.run_id)
        assert row["total_input_tokens"] == 42
        assert row["total_output_tokens"] == 99

    @pytest.mark.asyncio
    async def test_save_run_persists_feedback_cycles(
        self, minimal_pipeline_run, minimal_customer_config
    ):
        minimal_pipeline_run.feedback_cycles = {
            "code_revisions": 1,
            "design_revisions": 0,
        }
        await save_run(minimal_pipeline_run, minimal_customer_config)
        row = await get_run(minimal_pipeline_run.run_id)
        cycles = json.loads(row["feedback_cycles_json"])
        assert cycles["code_revisions"] == 1
        assert cycles["design_revisions"] == 0

    @pytest.mark.asyncio
    async def test_save_run_completed_at_is_null_by_default(
        self, minimal_pipeline_run, minimal_customer_config
    ):
        await save_run(minimal_pipeline_run, minimal_customer_config)
        row = await get_run(minimal_pipeline_run.run_id)
        assert row["completed_at"] is None

    @pytest.mark.asyncio
    async def test_save_run_outcome_is_null_by_default(
        self, minimal_pipeline_run, minimal_customer_config
    ):
        await save_run(minimal_pipeline_run, minimal_customer_config)
        row = await get_run(minimal_pipeline_run.run_id)
        assert row["outcome"] is None


# ---------------------------------------------------------------------------
# 5. update_run
# ---------------------------------------------------------------------------


class TestUpdateRun:
    @pytest.mark.asyncio
    async def test_update_run_changes_state(
        self, minimal_pipeline_run, minimal_customer_config
    ):
        await save_run(minimal_pipeline_run, minimal_customer_config)
        minimal_pipeline_run.state = PipelineState.COMPLETE
        await update_run(minimal_pipeline_run)
        row = await get_run(minimal_pipeline_run.run_id)
        assert row["state"] == PipelineState.COMPLETE.value

    @pytest.mark.asyncio
    async def test_update_run_sets_completed_at(
        self, minimal_pipeline_run, minimal_customer_config
    ):
        await save_run(minimal_pipeline_run, minimal_customer_config)
        minimal_pipeline_run.completed_at = datetime.now(timezone.utc)
        minimal_pipeline_run.state = PipelineState.COMPLETE
        await update_run(minimal_pipeline_run)
        row = await get_run(minimal_pipeline_run.run_id)
        assert row["completed_at"] is not None
        parsed = datetime.fromisoformat(row["completed_at"])
        assert parsed is not None

    @pytest.mark.asyncio
    async def test_update_run_sets_outcome(
        self, minimal_pipeline_run, minimal_customer_config
    ):
        await save_run(minimal_pipeline_run, minimal_customer_config)
        minimal_pipeline_run.outcome = "success"
        await update_run(minimal_pipeline_run)
        row = await get_run(minimal_pipeline_run.run_id)
        assert row["outcome"] == "success"

    @pytest.mark.asyncio
    async def test_update_run_updates_token_counts(
        self, minimal_pipeline_run, minimal_customer_config
    ):
        await save_run(minimal_pipeline_run, minimal_customer_config)
        minimal_pipeline_run.total_tokens = TokenUsage(
            input_tokens=500, output_tokens=1000
        )
        await update_run(minimal_pipeline_run)
        row = await get_run(minimal_pipeline_run.run_id)
        assert row["total_input_tokens"] == 500
        assert row["total_output_tokens"] == 1000

    @pytest.mark.asyncio
    async def test_update_run_updates_feedback_cycles(
        self, minimal_pipeline_run, minimal_customer_config
    ):
        await save_run(minimal_pipeline_run, minimal_customer_config)
        minimal_pipeline_run.feedback_cycles = {
            "code_revisions": 2,
            "design_revisions": 1,
        }
        await update_run(minimal_pipeline_run)
        row = await get_run(minimal_pipeline_run.run_id)
        cycles = json.loads(row["feedback_cycles_json"])
        assert cycles["code_revisions"] == 2
        assert cycles["design_revisions"] == 1

    @pytest.mark.asyncio
    async def test_update_run_completed_at_none_stores_null(
        self, minimal_pipeline_run, minimal_customer_config
    ):
        await save_run(minimal_pipeline_run, minimal_customer_config)
        minimal_pipeline_run.completed_at = None
        await update_run(minimal_pipeline_run)
        row = await get_run(minimal_pipeline_run.run_id)
        assert row["completed_at"] is None


# ---------------------------------------------------------------------------
# 6. get_run — returns None for unknown run_id
# ---------------------------------------------------------------------------


class TestGetRunUnknown:
    @pytest.mark.asyncio
    async def test_get_run_returns_none_for_unknown_run_id(self):
        result = await get_run("nonexistent-run-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_run_returns_none_for_empty_string_run_id(self):
        result = await get_run("")
        assert result is None


# ---------------------------------------------------------------------------
# 7. save_event + get_events roundtrip
# ---------------------------------------------------------------------------


class TestSaveEventAndGetEvents:
    @pytest.mark.asyncio
    async def test_save_and_get_event_returns_matching_event_id(
        self, minimal_pipeline_run, minimal_customer_config, minimal_event
    ):
        await save_run(minimal_pipeline_run, minimal_customer_config)
        await save_event(minimal_event)
        rows = await get_events(minimal_pipeline_run.run_id)
        assert len(rows) == 1
        assert rows[0]["event_id"] == minimal_event.event_id

    @pytest.mark.asyncio
    async def test_save_event_persists_run_id(
        self, minimal_pipeline_run, minimal_customer_config, minimal_event
    ):
        await save_run(minimal_pipeline_run, minimal_customer_config)
        await save_event(minimal_event)
        rows = await get_events(minimal_pipeline_run.run_id)
        assert rows[0]["run_id"] == minimal_pipeline_run.run_id

    @pytest.mark.asyncio
    async def test_save_event_persists_agent(
        self, minimal_pipeline_run, minimal_customer_config, minimal_event
    ):
        await save_run(minimal_pipeline_run, minimal_customer_config)
        await save_event(minimal_event)
        rows = await get_events(minimal_pipeline_run.run_id)
        assert rows[0]["agent"] == AgentName.SYSTEM.value

    @pytest.mark.asyncio
    async def test_save_event_persists_event_type(
        self, minimal_pipeline_run, minimal_customer_config, minimal_event
    ):
        await save_run(minimal_pipeline_run, minimal_customer_config)
        await save_event(minimal_event)
        rows = await get_events(minimal_pipeline_run.run_id)
        assert rows[0]["event_type"] == EventType.PIPELINE_STARTED.value

    @pytest.mark.asyncio
    async def test_save_event_persists_message(
        self, minimal_pipeline_run, minimal_customer_config, minimal_event
    ):
        await save_run(minimal_pipeline_run, minimal_customer_config)
        await save_event(minimal_event)
        rows = await get_events(minimal_pipeline_run.run_id)
        assert rows[0]["message"] == "Pipeline started"

    @pytest.mark.asyncio
    async def test_save_event_persists_tokens_used(
        self, minimal_pipeline_run, minimal_customer_config
    ):
        await save_run(minimal_pipeline_run, minimal_customer_config)
        event = PipelineEvent(
            event_id="evt-tokens-001",
            run_id=minimal_pipeline_run.run_id,
            agent=AgentName.REQUIREMENTS_ANALYST,
            event_type=EventType.AGENT_COMPLETE,
            message="Agent done",
            tokens_used=TokenUsage(input_tokens=150, output_tokens=300),
        )
        await save_event(event)
        rows = await get_events(minimal_pipeline_run.run_id)
        assert rows[0]["input_tokens"] == 150
        assert rows[0]["output_tokens"] == 300

    @pytest.mark.asyncio
    async def test_save_event_with_no_tokens_stores_zero(
        self, minimal_pipeline_run, minimal_customer_config
    ):
        await save_run(minimal_pipeline_run, minimal_customer_config)
        event = PipelineEvent(
            event_id="evt-no-tokens-001",
            run_id=minimal_pipeline_run.run_id,
            agent=AgentName.SYSTEM,
            event_type=EventType.PIPELINE_STARTED,
            message="No tokens here",
            tokens_used=None,
        )
        await save_event(event)
        rows = await get_events(minimal_pipeline_run.run_id)
        assert rows[0]["input_tokens"] == 0
        assert rows[0]["output_tokens"] == 0

    @pytest.mark.asyncio
    async def test_save_event_persists_duration_ms(
        self, minimal_pipeline_run, minimal_customer_config
    ):
        await save_run(minimal_pipeline_run, minimal_customer_config)
        event = PipelineEvent(
            event_id="evt-duration-001",
            run_id=minimal_pipeline_run.run_id,
            agent=AgentName.DEVELOPER,
            event_type=EventType.AGENT_COMPLETE,
            message="Done",
            duration_ms=4200,
        )
        await save_event(event)
        rows = await get_events(minimal_pipeline_run.run_id)
        assert rows[0]["duration_ms"] == 4200

    @pytest.mark.asyncio
    async def test_save_event_persists_pipeline_state(
        self, minimal_pipeline_run, minimal_customer_config
    ):
        await save_run(minimal_pipeline_run, minimal_customer_config)
        event = PipelineEvent(
            event_id="evt-state-001",
            run_id=minimal_pipeline_run.run_id,
            agent=AgentName.SYSTEM,
            event_type=EventType.PIPELINE_STARTED,
            message="In design phase",
            pipeline_state=PipelineState.DESIGN,
        )
        await save_event(event)
        rows = await get_events(minimal_pipeline_run.run_id)
        assert rows[0]["pipeline_state"] == PipelineState.DESIGN.value

    @pytest.mark.asyncio
    async def test_save_event_with_no_pipeline_state_stores_null(
        self, minimal_pipeline_run, minimal_customer_config, minimal_event
    ):
        await save_run(minimal_pipeline_run, minimal_customer_config)
        await save_event(minimal_event)
        rows = await get_events(minimal_pipeline_run.run_id)
        assert rows[0]["pipeline_state"] is None

    @pytest.mark.asyncio
    async def test_save_event_persists_data_as_json(
        self, minimal_pipeline_run, minimal_customer_config
    ):
        await save_run(minimal_pipeline_run, minimal_customer_config)
        event = PipelineEvent(
            event_id="evt-data-001",
            run_id=minimal_pipeline_run.run_id,
            agent=AgentName.SYSTEM,
            event_type=EventType.PROGRESS_UPDATE,
            message="Progress",
            data={"step": "analysis", "progress": 50},
        )
        await save_event(event)
        rows = await get_events(minimal_pipeline_run.run_id)
        data = json.loads(rows[0]["data_json"])
        assert data["step"] == "analysis"
        assert data["progress"] == 50

    @pytest.mark.asyncio
    async def test_save_event_persists_timestamp(
        self, minimal_pipeline_run, minimal_customer_config, minimal_event
    ):
        await save_run(minimal_pipeline_run, minimal_customer_config)
        await save_event(minimal_event)
        rows = await get_events(minimal_pipeline_run.run_id)
        assert rows[0]["timestamp"] is not None
        parsed = datetime.fromisoformat(rows[0]["timestamp"])
        assert parsed is not None


# ---------------------------------------------------------------------------
# 8. get_events ordering by timestamp
# ---------------------------------------------------------------------------


class TestGetEventsOrdering:
    @pytest.mark.asyncio
    async def test_get_events_returns_events_ordered_by_timestamp_ascending(
        self, minimal_pipeline_run, minimal_customer_config
    ):
        await save_run(minimal_pipeline_run, minimal_customer_config)

        # Create events with explicit, distinct timestamps to force ordering
        t1 = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2025, 1, 1, 10, 0, 1, tzinfo=timezone.utc)
        t3 = datetime(2025, 1, 1, 10, 0, 2, tzinfo=timezone.utc)

        event_a = PipelineEvent(
            event_id="evt-order-003",
            run_id=minimal_pipeline_run.run_id,
            timestamp=t3,
            agent=AgentName.DEVELOPER,
            event_type=EventType.AGENT_COMPLETE,
            message="Third",
        )
        event_b = PipelineEvent(
            event_id="evt-order-001",
            run_id=minimal_pipeline_run.run_id,
            timestamp=t1,
            agent=AgentName.SYSTEM,
            event_type=EventType.PIPELINE_STARTED,
            message="First",
        )
        event_c = PipelineEvent(
            event_id="evt-order-002",
            run_id=minimal_pipeline_run.run_id,
            timestamp=t2,
            agent=AgentName.REQUIREMENTS_ANALYST,
            event_type=EventType.AGENT_START,
            message="Second",
        )

        # Insert in non-chronological order
        await save_event(event_a)
        await save_event(event_b)
        await save_event(event_c)

        rows = await get_events(minimal_pipeline_run.run_id)
        assert len(rows) == 3
        assert rows[0]["message"] == "First"
        assert rows[1]["message"] == "Second"
        assert rows[2]["message"] == "Third"


# ---------------------------------------------------------------------------
# 9. get_events — empty list for unknown run_id
# ---------------------------------------------------------------------------


class TestGetEventsUnknownRun:
    @pytest.mark.asyncio
    async def test_get_events_returns_empty_list_for_unknown_run_id(self):
        rows = await get_events("nonexistent-run-id")
        assert rows == []

    @pytest.mark.asyncio
    async def test_get_events_returns_empty_list_for_run_with_no_events(
        self, minimal_pipeline_run, minimal_customer_config
    ):
        await save_run(minimal_pipeline_run, minimal_customer_config)
        rows = await get_events(minimal_pipeline_run.run_id)
        assert rows == []


# ---------------------------------------------------------------------------
# 10. Multiple events for same run_id
# ---------------------------------------------------------------------------


class TestMultipleEventsPerRun:
    @pytest.mark.asyncio
    async def test_get_events_returns_all_events_for_run(
        self, minimal_pipeline_run, minimal_customer_config
    ):
        await save_run(minimal_pipeline_run, minimal_customer_config)

        agents_and_types = [
            (AgentName.SYSTEM, EventType.PIPELINE_STARTED),
            (AgentName.REQUIREMENTS_ANALYST, EventType.AGENT_START),
            (AgentName.REQUIREMENTS_ANALYST, EventType.AGENT_COMPLETE),
            (AgentName.SOLUTION_ARCHITECT, EventType.AGENT_START),
            (AgentName.SOLUTION_ARCHITECT, EventType.AGENT_COMPLETE),
        ]

        for i, (agent, event_type) in enumerate(agents_and_types):
            event = PipelineEvent(
                event_id=f"evt-multi-{i:03d}",
                run_id=minimal_pipeline_run.run_id,
                agent=agent,
                event_type=event_type,
                message=f"Event {i}",
            )
            await save_event(event)

        rows = await get_events(minimal_pipeline_run.run_id)
        assert len(rows) == 5

    @pytest.mark.asyncio
    async def test_get_events_does_not_return_events_from_other_run(
        self, minimal_customer_config
    ):
        run_a = PipelineRun(run_id="run-aaa-001")
        run_b = PipelineRun(run_id="run-bbb-001")

        await save_run(run_a, minimal_customer_config)
        await save_run(run_b, minimal_customer_config)

        event_a = PipelineEvent(
            event_id="evt-run-a-001",
            run_id=run_a.run_id,
            agent=AgentName.SYSTEM,
            event_type=EventType.PIPELINE_STARTED,
            message="Run A event",
        )
        event_b = PipelineEvent(
            event_id="evt-run-b-001",
            run_id=run_b.run_id,
            agent=AgentName.SYSTEM,
            event_type=EventType.PIPELINE_STARTED,
            message="Run B event",
        )

        await save_event(event_a)
        await save_event(event_b)

        rows_a = await get_events(run_a.run_id)
        rows_b = await get_events(run_b.run_id)

        assert len(rows_a) == 1
        assert rows_a[0]["event_id"] == "evt-run-a-001"

        assert len(rows_b) == 1
        assert rows_b[0]["event_id"] == "evt-run-b-001"

    @pytest.mark.asyncio
    async def test_get_events_event_ids_are_all_distinct(
        self, minimal_pipeline_run, minimal_customer_config
    ):
        await save_run(minimal_pipeline_run, minimal_customer_config)

        for i in range(3):
            event = PipelineEvent(
                event_id=f"evt-distinct-{i:03d}",
                run_id=minimal_pipeline_run.run_id,
                agent=AgentName.SYSTEM,
                event_type=EventType.PROGRESS_UPDATE,
                message=f"Progress {i}",
            )
            await save_event(event)

        rows = await get_events(minimal_pipeline_run.run_id)
        event_ids = [r["event_id"] for r in rows]
        assert len(event_ids) == len(set(event_ids))
