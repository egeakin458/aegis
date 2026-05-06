"""
Tests for the RunnerManager (pipeline/manager.py).

Tests lifecycle management, event queue, cleanup, and error handling.
Uses mock agents to avoid real LLM calls.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.pipeline.manager import RunnerEntry, RunnerManager, _create_agents
from app.schemas.customer_config import CustomerConfigV2
from app.schemas.pipeline_events import (
    AgentName,
    EventType,
    PipelineEvent,
    PipelineRun,
    PipelineState,
)


@pytest.fixture
def minimal_config(ddc_ecommerce) -> CustomerConfigV2:
    return ddc_ecommerce


@pytest.fixture
def manager() -> RunnerManager:
    return RunnerManager()


class TestRunnerEntry:
    def test_entry_defaults(self):
        runner = MagicMock()
        entry = RunnerEntry(runner=runner, run_id="test-123")
        assert entry.run_id == "test-123"
        assert entry.task is None
        assert entry.customer_config is None
        assert entry.event_queue.maxsize == 1000
        assert entry.created_at is not None


class TestCreateAgents:
    def test_creates_all_four_agents(self):
        agents = _create_agents()
        assert "requirements_analyst" in agents
        assert "solution_architect" in agents
        assert "developer" in agents
        assert "qa_reviewer" in agents
        assert len(agents) == 4


class TestRunnerManager:
    def test_get_entry_returns_none_for_unknown(self, manager):
        assert manager.get_entry("nonexistent") is None

    @pytest.mark.asyncio
    async def test_start_run_returns_run_id(self, manager, minimal_config):
        """start_run returns a UUID string and registers the entry."""
        with (
            patch("app.pipeline.manager._create_agents") as mock_agents,
            patch("app.pipeline.manager.repo") as mock_repo,
        ):
            # Mock agents — the background task will fail at LLM call,
            # but we only care about start_run returning a run_id.
            mock_ra = AsyncMock()
            mock_agents.return_value = {
                "requirements_analyst": mock_ra,
                "solution_architect": AsyncMock(),
                "developer": AsyncMock(),
                "qa_reviewer": AsyncMock(),
            }
            mock_repo.save_run = AsyncMock()
            mock_repo.save_event = AsyncMock()
            mock_repo.update_run = AsyncMock()

            run_id = await manager.start_run(minimal_config)

            assert isinstance(run_id, str)
            assert len(run_id) > 0

            # Entry is registered
            entry = manager.get_entry(run_id)
            assert entry is not None
            assert entry.run_id == run_id
            assert entry.customer_config == minimal_config
            assert entry.task is not None

            # Cancel the background task to avoid warnings
            entry.task.cancel()
            try:
                await entry.task
            except (asyncio.CancelledError, Exception):
                pass

    @pytest.mark.asyncio
    async def test_start_run_persists_to_db(self, manager, minimal_config):
        """start_run calls repo.save_run with the initial PipelineRun."""
        with (
            patch("app.pipeline.manager._create_agents") as mock_agents,
            patch("app.pipeline.manager.repo") as mock_repo,
        ):
            mock_agents.return_value = {
                "requirements_analyst": AsyncMock(),
                "solution_architect": AsyncMock(),
                "developer": AsyncMock(),
                "qa_reviewer": AsyncMock(),
            }
            mock_repo.save_run = AsyncMock()
            mock_repo.save_event = AsyncMock()
            mock_repo.update_run = AsyncMock()

            run_id = await manager.start_run(minimal_config)

            mock_repo.save_run.assert_called_once()
            args = mock_repo.save_run.call_args
            saved_run = args[0][0]
            assert isinstance(saved_run, PipelineRun)
            assert saved_run.run_id == run_id

            # Cleanup
            entry = manager.get_entry(run_id)
            entry.task.cancel()
            try:
                await entry.task
            except (asyncio.CancelledError, Exception):
                pass

    @pytest.mark.asyncio
    async def test_resume_run_raises_on_unknown_id(self, manager):
        with pytest.raises(KeyError, match="not found"):
            await manager.resume_run("nonexistent", {"q1": "answer"})

    @pytest.mark.asyncio
    async def test_resume_run_raises_if_not_clarification(self, manager, minimal_config):
        """resume raises ValueError if run is not in CLARIFICATION state."""
        with (
            patch("app.pipeline.manager._create_agents") as mock_agents,
            patch("app.pipeline.manager.repo") as mock_repo,
        ):
            mock_agents.return_value = {
                "requirements_analyst": AsyncMock(),
                "solution_architect": AsyncMock(),
                "developer": AsyncMock(),
                "qa_reviewer": AsyncMock(),
            }
            mock_repo.save_run = AsyncMock()
            mock_repo.save_event = AsyncMock()
            mock_repo.update_run = AsyncMock()

            run_id = await manager.start_run(minimal_config)
            # State is INTAKE initially, not CLARIFICATION
            entry = manager.get_entry(run_id)
            entry.task.cancel()
            try:
                await entry.task
            except (asyncio.CancelledError, Exception):
                pass

            # Force state to something other than CLARIFICATION
            entry.runner.current_run.state = PipelineState.DESIGN

            with pytest.raises(ValueError, match="not in CLARIFICATION"):
                await manager.resume_run(run_id, {"q1": "answer"})

    @pytest.mark.asyncio
    async def test_emit_callback_pushes_to_queue(self, manager):
        """The emit callback created by _make_emit_callback puts events on the queue."""
        runner = MagicMock()
        entry = RunnerEntry(runner=runner, run_id="test-run")
        callback = manager._make_emit_callback(entry)

        event = PipelineEvent(
            run_id="test-run",
            agent=AgentName.SYSTEM,
            event_type=EventType.PIPELINE_STARTED,
            message="Test event",
        )

        with patch("app.pipeline.manager.repo") as mock_repo:
            mock_repo.save_event = AsyncMock()
            callback(event)

        assert not entry.event_queue.empty()
        queued_event = entry.event_queue.get_nowait()
        assert queued_event.event_id == event.event_id

    @pytest.mark.asyncio
    async def test_cleanup_removes_old_completed_runs(self, manager):
        """cleanup_completed removes entries older than max_age_seconds."""
        runner = MagicMock()
        run = PipelineRun()
        run.completed_at = datetime.now(timezone.utc) - timedelta(hours=2)
        run.state = PipelineState.COMPLETE
        runner.current_run = run

        entry = RunnerEntry(runner=runner, run_id=run.run_id)
        manager._entries[run.run_id] = entry

        removed = await manager.cleanup_completed(max_age_seconds=3600)
        assert removed == 1
        assert manager.get_entry(run.run_id) is None

    @pytest.mark.asyncio
    async def test_cleanup_keeps_recent_completed_runs(self, manager):
        """cleanup_completed does NOT remove entries newer than max_age_seconds."""
        runner = MagicMock()
        run = PipelineRun()
        run.completed_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        run.state = PipelineState.COMPLETE
        runner.current_run = run

        entry = RunnerEntry(runner=runner, run_id=run.run_id)
        manager._entries[run.run_id] = entry

        removed = await manager.cleanup_completed(max_age_seconds=3600)
        assert removed == 0
        assert manager.get_entry(run.run_id) is not None

    @pytest.mark.asyncio
    async def test_cleanup_keeps_active_runs(self, manager):
        """cleanup_completed does NOT remove runs without completed_at."""
        runner = MagicMock()
        run = PipelineRun()
        run.completed_at = None
        runner.current_run = run

        entry = RunnerEntry(runner=runner, run_id=run.run_id)
        manager._entries[run.run_id] = entry

        removed = await manager.cleanup_completed(max_age_seconds=0)
        assert removed == 0


class TestFinalizeRunOrdering:
    """PIPELINE_COMPLETE must reach the SSE queue only after save_output() writes manifest."""

    @pytest.mark.asyncio
    async def test_terminal_event_emitted_after_save_output(self, manager, ddc_ecommerce):
        from app.pipeline.runner import PipelineRunner
        from app.schemas.agent_outputs import CodeOutput

        # Track whether the SSE queue already had an event when save_output ran.
        # If the ordering is correct, the queue is empty during save and non-empty after.
        queue_state_during_save: list[bool] = []

        entry = RunnerEntry(runner=None, run_id="test-ordering")  # type: ignore[arg-type]
        runner = PipelineRunner(
            agents={
                "requirements_analyst": MagicMock(),
                "solution_architect": MagicMock(),
                "developer": MagicMock(),
                "qa_reviewer": MagicMock(),
            },
            emit_event=manager._make_emit_callback(entry),
        )
        entry.runner = runner

        run = PipelineRun()
        run.run_id = "test-ordering"
        run.state = PipelineState.COMPLETE
        run.outcome = "success"
        runner.current_run = run
        runner.context = {"code_output": MagicMock(spec=CodeOutput)}

        async def fake_save(run_id, code_output):
            queue_state_during_save.append(entry.event_queue.empty())

        with (
            patch("app.pipeline.manager.repo") as mock_repo,
            patch("app.pipeline.manager.save_output", side_effect=fake_save),
        ):
            mock_repo.update_run = AsyncMock()
            mock_repo.save_event = AsyncMock()
            await manager._finalize_run(entry)

        # save_output ran before the event was pushed to the queue
        assert queue_state_during_save == [True], (
            "PIPELINE_COMPLETE was already in the SSE queue when save_output ran — race condition!"
        )
        # After _finalize_run the terminal event IS in the queue
        assert not entry.event_queue.empty()
        event = entry.event_queue.get_nowait()
        assert event.event_type == EventType.PIPELINE_COMPLETE
