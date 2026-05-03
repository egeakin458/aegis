"""
Runner Manager — lifecycle management for pipeline runs.

Bridges the HTTP/API layer and the PipelineRunner engine.
Manages active runners, event queues for SSE streaming,
background task execution, and database persistence.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.agents import Developer, QAReviewer, RequirementsAnalyst, SolutionArchitect
from app.db import repositories as repo
from app.pipeline.output_storage import save_output
from app.pipeline.runner import PipelineRunner
from app.schemas.customer_config import CustomerConfigV2
from app.schemas.pipeline_events import (
    AgentName,
    EventType,
    PipelineEvent,
    PipelineRun,
    PipelineState,
)

logger = logging.getLogger(__name__)

_EVENT_QUEUE_SIZE = 1000


@dataclass
class RunnerEntry:
    """Holds all state for a single pipeline run."""

    runner: PipelineRunner
    run_id: str
    task: Optional[asyncio.Task] = None
    event_queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=_EVENT_QUEUE_SIZE))
    customer_config: Optional[CustomerConfigV2] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def _create_agents() -> dict:
    """Instantiate the four pipeline agents."""
    return {
        "requirements_analyst": RequirementsAnalyst(),
        "solution_architect": SolutionArchitect(),
        "developer": Developer(),
        "qa_reviewer": QAReviewer(),
    }


class RunnerManager:
    """Manages active pipeline runners and their lifecycle."""

    def __init__(self) -> None:
        self._entries: dict[str, RunnerEntry] = {}

    def _make_emit_callback(self, entry: RunnerEntry):
        """Create an event callback that persists to DB and pushes to SSE queue."""

        def callback(event: PipelineEvent) -> None:
            # Push to SSE queue (sync-safe)
            try:
                entry.event_queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(
                    "Event queue full for run %s, event dropped from SSE stream",
                    entry.run_id,
                )

            # Persist to SQLite (fire-and-forget async task with error handling)
            async def _persist_event(ev: PipelineEvent) -> None:
                try:
                    await repo.save_event(ev)
                except Exception as exc:
                    logger.error("Failed to persist event %s: %s", ev.event_id, exc)

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(_persist_event(event))
            except RuntimeError:
                logger.warning("No event loop for DB persist of event %s", event.event_id)

        return callback

    async def _finalize_run(self, entry: RunnerEntry) -> None:
        """Update DB and save output after a run completes or pauses."""
        runner = entry.runner
        if runner.current_run:
            await repo.update_run(runner.current_run)

        if (
            runner.current_run
            and runner.current_run.state == PipelineState.COMPLETE
            and runner.current_run.outcome in ("success", "partial")
            and "code_output" in runner.context
        ):
            try:
                await save_output(runner.current_run.run_id, runner.context["code_output"])
            except (OSError, ValueError) as e:
                logger.error("Failed to save output for run %s: %s", entry.run_id, e)

    async def start_run(self, config: CustomerConfigV2) -> str:
        """
        Start a new pipeline run.

        Creates agents, wires up event callbacks, launches the pipeline
        as a background task, and persists the initial run to SQLite.

        Returns the run_id.
        """
        agents = _create_agents()

        # Pre-create PipelineRun so we have the run_id before the task starts.
        # We then drive the runner's internal methods directly instead of calling
        # runner.run(), which would overwrite current_run with a new instance.
        pre_run = PipelineRun()

        entry = RunnerEntry(
            runner=None,  # Set after runner creation
            run_id=pre_run.run_id,
            customer_config=config,
        )

        # Wire emit callback (pushes to queue + persists to DB)
        runner = PipelineRunner(agents=agents, emit_event=self._make_emit_callback(entry))
        runner.current_run = pre_run
        entry.runner = runner
        self._entries[entry.run_id] = entry

        # Persist initial run to DB
        await repo.save_run(pre_run, config)

        # Launch pipeline as background task
        async def _execute():
            try:
                runner.context = {"customer_config_v2": config}
                runner.clarification_history = []
                runner.code_revision_count = 0
                runner.design_revision_count = 0

                runner._transition(PipelineState.INTAKE)
                runner.emit_event(PipelineEvent(
                    run_id=pre_run.run_id,
                    agent=AgentName.SYSTEM,
                    event_type=EventType.PIPELINE_STARTED,
                    message="Aegis is starting work on your project.",
                ))

                try:
                    await runner._run_from_state(PipelineState.REQUIREMENTS)
                except Exception as e:
                    await runner._handle_failure(e)

                await self._finalize_run(entry)
            except Exception as e:
                logger.error("Pipeline run %s failed: %s", entry.run_id, e, exc_info=True)

        entry.task = asyncio.create_task(_execute())
        entry.task.add_done_callback(self._on_task_done)
        return entry.run_id

    async def resume_run(self, run_id: str, answers: dict[str, str]) -> None:
        """
        Resume a paused pipeline after clarification answers.

        Raises ValueError if the run is not in CLARIFICATION state.
        Raises KeyError if run_id is not found.
        """
        entry = self._entries.get(run_id)
        if entry is None:
            raise KeyError(f"Run {run_id} not found")

        runner = entry.runner
        if not runner.current_run or runner.current_run.state != PipelineState.CLARIFICATION:
            raise ValueError(f"Run {run_id} is not in CLARIFICATION state")

        async def _resume():
            try:
                await runner.resume(answers)
                await self._finalize_run(entry)
            except Exception as e:
                logger.error("Resume failed for run %s: %s", run_id, e, exc_info=True)

        entry.task = asyncio.create_task(_resume())
        entry.task.add_done_callback(self._on_task_done)

    @staticmethod
    def _on_task_done(task: asyncio.Task) -> None:
        """Log unhandled exceptions from background pipeline tasks."""
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            logger.error("Background pipeline task failed: %s", exc)

    def get_entry(self, run_id: str) -> RunnerEntry | None:
        """Look up a runner entry by run_id."""
        return self._entries.get(run_id)

    async def cleanup_completed(self, max_age_seconds: int = 3600) -> int:
        """
        Remove entries for runs that completed more than max_age_seconds ago.

        Returns the number of entries removed.
        """
        now = datetime.now(timezone.utc)
        to_remove = []
        for run_id, entry in self._entries.items():
            run = entry.runner.current_run
            if run and run.completed_at:
                age = (now - run.completed_at).total_seconds()
                if age > max_age_seconds:
                    to_remove.append(run_id)

        for run_id in to_remove:
            del self._entries[run_id]

        if to_remove:
            logger.info("Cleaned up %d completed pipeline entries", len(to_remove))
        return len(to_remove)


# Singleton instance
runner_manager = RunnerManager()
