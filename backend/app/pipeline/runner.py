"""
Pipeline Runner — the Aegis orchestration engine.

A state machine that manages the sequence of agent execution,
context passing, feedback loops, and event emission. This is the
core intellectual contribution of the thesis — custom orchestration
without any agent framework.

State transitions:
    INTAKE → REQUIREMENTS → [CLARIFICATION ↔ REQUIREMENTS] → DESIGN →
    DEVELOPMENT → REVIEW → COMPLETE
                    ↑          ↓
            CODE_REVISION ← revise_code (max 2)
                    ↑          ↓
           DESIGN_REVISION ← revise_design (max 1) → DESIGN → ...

Clarification uses Option B: pipeline persists state and terminates.
A POST /clarification/{run_id} resumes the pipeline with answers.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Optional
from uuid import uuid4

from app.agents.base import BaseAgent
from app.config import settings
from app.pipeline.build_checker import run_build_check
from app.schemas.customer_config import (
    ClarificationRound,
    CustomerConfig,
    FinalizedConfig,
)
from app.schemas.pipeline_events import (
    AgentName,
    EventType,
    PipelineEvent,
    PipelineRun,
    PipelineState,
    TokenUsage,
)
from app.schemas.ra_output import RAOutput

logger = logging.getLogger(__name__)


class PipelineRunner:
    """
    Orchestrates the Aegis agent pipeline.

    Usage:
        runner = PipelineRunner(
            agents={"requirements_analyst": ra, "solution_architect": sa, ...},
            emit_event=callback,
        )
        result = await runner.run(customer_config)

    For clarification loop (Option B):
        result = await runner.run(customer_config)
        # result.state == CLARIFICATION → pipeline paused
        # Customer answers arrive via API
        result = await runner.resume(run_id, answers)
    """

    def __init__(
        self,
        agents: dict[str, BaseAgent],
        emit_event: Optional[Callable[[PipelineEvent], None]] = None,
    ) -> None:
        self.agents = agents
        self._emit = emit_event or (lambda e: None)

        # Pipeline run state
        self.current_run: Optional[PipelineRun] = None
        self.context: dict[str, Any] = {}
        self.clarification_history: list[ClarificationRound] = []
        self.code_revision_count: int = 0
        self.design_revision_count: int = 0

        self._state_handlers: dict[PipelineState, Callable[[], Awaitable[PipelineState]]] = {
            PipelineState.REQUIREMENTS: self._run_requirements,
            PipelineState.DESIGN: self._run_design,
            PipelineState.DEVELOPMENT: self._run_development,
            PipelineState.BUILD_CHECK: self._run_build_check,
            PipelineState.REVIEW: self._run_review,
            PipelineState.CODE_REVISION: self._run_code_revision,
            PipelineState.DESIGN_REVISION: self._run_design_revision,
        }

    def emit_event(self, event: PipelineEvent) -> None:
        """Emit an event and add it to the run log."""
        if self.current_run:
            event.pipeline_state = self.current_run.state
            self.current_run.events.append(event)
            if event.tokens_used:
                self.current_run.total_tokens.input_tokens += event.tokens_used.input_tokens
                self.current_run.total_tokens.output_tokens += event.tokens_used.output_tokens
        self._emit(event)

    async def run(self, customer_config: CustomerConfig) -> PipelineRun:
        """
        Start a new pipeline run from a customer config.

        Returns the PipelineRun. If state is CLARIFICATION, the pipeline
        is paused waiting for customer answers. Call resume() to continue.
        """
        self.current_run = PipelineRun()
        self.context = {"customer_config": customer_config}
        self.clarification_history = []
        self.code_revision_count = 0
        self.design_revision_count = 0

        self._transition(PipelineState.INTAKE)
        self.emit_event(PipelineEvent(
            run_id=self.current_run.run_id,
            agent=AgentName.SYSTEM,
            event_type=EventType.PIPELINE_STARTED,
            message="Aegis is starting work on your project.",
        ))

        try:
            await self._run_from_state(PipelineState.REQUIREMENTS)
        except Exception as e:
            await self._handle_failure(e)

        return self.current_run

    async def resume(
        self, answers: dict[str, str]
    ) -> PipelineRun:
        """
        Resume a paused pipeline after customer provides clarification answers.

        Args:
            answers: dict mapping question IDs to customer answer strings
        """
        if not self.current_run or self.current_run.state != PipelineState.CLARIFICATION:
            raise ValueError("Pipeline is not in CLARIFICATION state")

        # Record the answers in the current clarification round
        if self.clarification_history:
            current_round = self.clarification_history[-1]
            current_round.answers = answers

        self.emit_event(PipelineEvent(
            run_id=self.current_run.run_id,
            agent=AgentName.REQUIREMENTS_ANALYST,
            event_type=EventType.CLARIFICATION_RECEIVED,
            message="Your answers have been received. Our analyst is reviewing them.",
            data={"round": len(self.clarification_history), "answers": answers},
        ))

        try:
            await self._run_from_state(PipelineState.REQUIREMENTS)
        except Exception as e:
            await self._handle_failure(e)

        return self.current_run

    async def _run_from_state(self, start_state: PipelineState) -> None:
        """Execute the pipeline from a given state forward."""
        state = start_state

        while state not in (PipelineState.COMPLETE, PipelineState.FAILED, PipelineState.CLARIFICATION):
            self._transition(state)

            handler = self._state_handlers.get(state)
            if handler is None:
                raise ValueError(f"No handler registered for state: {state}")
            state = await handler()

        # Handle terminal states
        if state == PipelineState.COMPLETE:
            self._transition(PipelineState.COMPLETE)
            self.current_run.completed_at = datetime.now(timezone.utc)
            if self.current_run.outcome == "partial":
                self.emit_event(PipelineEvent(
                    run_id=self.current_run.run_id,
                    agent=AgentName.SYSTEM,
                    event_type=EventType.PIPELINE_PARTIAL,
                    message="We built as much as we could within review cycles. Here's what was completed.",
                ))
            else:
                self.current_run.outcome = "success"
                self.emit_event(PipelineEvent(
                    run_id=self.current_run.run_id,
                    agent=AgentName.SYSTEM,
                    event_type=EventType.PIPELINE_COMPLETE,
                    message="Your application is ready! Here's what we built.",
                ))
        elif state == PipelineState.CLARIFICATION:
            self._transition(PipelineState.CLARIFICATION)
            # Pipeline pauses — will be resumed via resume()

    async def _run_requirements(self) -> PipelineState:
        """Run the Requirements Analyst agent."""
        ra = self.agents["requirements_analyst"]

        # Determine mode based on clarification state
        at_round_cap = len(self.clarification_history) >= settings.max_clarification_rounds
        mode = "finalize" if at_round_cap else "analyze"

        ra_context = {
            **self.context,
            "mode": mode,
            "clarification_history": self.clarification_history,
        }

        result: RAOutput = await ra.execute(
            ra_context, self.current_run.run_id, self.emit_event
        )

        if result.needs_clarification and not at_round_cap:
            # Store the questions as a new clarification round
            round_num = len(self.clarification_history) + 1
            new_round = ClarificationRound(
                round_number=round_num,
                questions=result.questions,
                answers=None,
            )
            self.clarification_history.append(new_round)

            self.emit_event(PipelineEvent(
                run_id=self.current_run.run_id,
                agent=AgentName.REQUIREMENTS_ANALYST,
                event_type=EventType.CLARIFICATION_NEEDED,
                message="Your analyst has a few questions to make sure we build exactly what you need.",
                data={
                    "round": round_num,
                    "questions": [q.model_dump() for q in result.questions],
                },
            ))
            return PipelineState.CLARIFICATION

        # Finalized — extract the config.
        # Guard against LLM misbehaviour at the round cap: if the model was
        # instructed to finalize but still returned needs_clarification=True,
        # finalized_config will be None (valid per the RAOutput schema when
        # needs_clarification=True). Surface a clear error rather than letting
        # an AttributeError propagate from the finalized.project_summary access below.
        if result.finalized_config is None:
            raise ValueError(
                "Requirements Analyst returned needs_clarification=True without a "
                "finalized_config after the clarification round cap was reached. "
                "The agent did not obey the finalize instruction."
            )
        finalized = result.finalized_config
        self.context["finalized_config"] = finalized

        self.emit_event(PipelineEvent(
            run_id=self.current_run.run_id,
            agent=AgentName.REQUIREMENTS_ANALYST,
            event_type=EventType.CONFIG_FINALIZED,
            message="Requirements confirmed! Here's your project brief.",
            data={
                "project_summary": finalized.project_summary,
                "assumptions_count": len(finalized.assumptions),
            },
        ))

        return PipelineState.DESIGN

    async def _run_design(self) -> PipelineState:
        """Run the Solution Architect agent."""
        sa = self.agents["solution_architect"]

        sa_context = {
            "finalized_config": self.context["finalized_config"],
        }

        result = await sa.execute(
            sa_context, self.current_run.run_id, self.emit_event
        )

        self.context["technical_design"] = result
        return PipelineState.DEVELOPMENT

    async def _run_development(self) -> PipelineState:
        """Run the Developer agent."""
        dev = self.agents["developer"]

        dev_context = {
            "finalized_config": self.context["finalized_config"],
            "technical_design": self.context["technical_design"],
        }

        result = await dev.execute(
            dev_context, self.current_run.run_id, self.emit_event
        )

        self.context["code_output"] = result
        return PipelineState.BUILD_CHECK

    async def _run_build_check(self) -> PipelineState:
        """Run syntax + structural verification on generated code."""
        code_output = self.context["code_output"]

        self.emit_event(PipelineEvent(
            run_id=self.current_run.run_id,
            agent=AgentName.SYSTEM,
            event_type=EventType.BUILD_CHECK_START,
            message="Verifying the generated code structure and syntax.",
        ))

        result = await run_build_check(code_output)
        self.context["build_check_result"] = result

        if result.passed:
            self.emit_event(PipelineEvent(
                run_id=self.current_run.run_id,
                agent=AgentName.SYSTEM,
                event_type=EventType.BUILD_CHECK_COMPLETE,
                message=f"Code verification passed. Checked {result.files_checked} files.",
                data={"files_checked": result.files_checked, "duration_ms": result.duration_ms},
            ))
            return PipelineState.REVIEW

        error_count = sum(1 for i in result.issues if i.severity == "error")
        self.emit_event(PipelineEvent(
            run_id=self.current_run.run_id,
            agent=AgentName.SYSTEM,
            event_type=EventType.BUILD_CHECK_FAILED,
            message=f"Found {error_count} issue(s) in the generated code. Sending back for fixes.",
            data={
                "error_count": error_count,
                "issues": [i.model_dump() for i in result.issues],
                "duration_ms": result.duration_ms,
            },
        ))

        if self.code_revision_count >= settings.max_code_revision_cycles:
            logger.info(
                "Build check failed but code revision cap reached (%d). Accepting partial output.",
                settings.max_code_revision_cycles,
            )
            self.current_run.outcome = "partial"
            return PipelineState.COMPLETE

        return PipelineState.CODE_REVISION

    async def _run_review(self) -> PipelineState:
        """Run the QA Reviewer agent."""
        qa = self.agents["qa_reviewer"]

        qa_context = {
            "finalized_config": self.context["finalized_config"],
            "technical_design": self.context["technical_design"],
            "code_output": self.context["code_output"],
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

    async def _run_code_revision(self) -> PipelineState:
        """Re-run the Developer agent with QA feedback."""
        self.code_revision_count += 1
        self.current_run.feedback_cycles["code_revisions"] = self.code_revision_count

        self.emit_event(PipelineEvent(
            run_id=self.current_run.run_id,
            agent=AgentName.SYSTEM,
            event_type=EventType.REVISION_STARTED,
            message=f"Our reviewer found some improvements. Sending back to the developer (revision {self.code_revision_count}).",
            data={
                "revision_type": "code",
                "revision_number": self.code_revision_count,
            },
        ))

        dev = self.agents["developer"]

        dev_context = {
            "finalized_config": self.context["finalized_config"],
            "technical_design": self.context["technical_design"],
            "previous_code": self.context["code_output"],
            "qa_review": self.context.get("qa_review"),
            "build_check_result": self.context.get("build_check_result"),
        }

        result = await dev.execute(
            dev_context, self.current_run.run_id, self.emit_event
        )

        self.context["code_output"] = result
        return PipelineState.REVIEW

    async def _run_design_revision(self) -> PipelineState:
        """Re-run the Solution Architect with QA feedback."""
        self.design_revision_count += 1
        self.current_run.feedback_cycles["design_revisions"] = self.design_revision_count

        self.emit_event(PipelineEvent(
            run_id=self.current_run.run_id,
            agent=AgentName.SYSTEM,
            event_type=EventType.REVISION_STARTED,
            message="Our reviewer identified a structural issue. Sending back to the architect for redesign.",
            data={
                "revision_type": "design",
                "revision_number": self.design_revision_count,
            },
        ))

        sa = self.agents["solution_architect"]

        sa_context = {
            "finalized_config": self.context["finalized_config"],
            "previous_design": self.context["technical_design"],
            "qa_review": self.context["qa_review"],
        }

        result = await sa.execute(
            sa_context, self.current_run.run_id, self.emit_event
        )

        self.context["technical_design"] = result
        return PipelineState.DEVELOPMENT

    async def _handle_failure(self, error: Exception) -> None:
        """Handle a pipeline failure."""
        self._transition(PipelineState.FAILED)
        self.current_run.completed_at = datetime.now(timezone.utc)
        self.current_run.outcome = "failed"

        self.emit_event(PipelineEvent(
            run_id=self.current_run.run_id,
            agent=AgentName.SYSTEM,
            event_type=EventType.PIPELINE_FAILED,
            message="We ran into an issue. Our team lead is looking into it.",
            data={"error": str(error)},
        ))

        logger.error("Pipeline run %s failed: %s", self.current_run.run_id, error, exc_info=True)

    def _transition(self, new_state: PipelineState) -> None:
        """Transition the pipeline to a new state."""
        if self.current_run:
            old_state = self.current_run.state
            self.current_run.state = new_state
            logger.info(
                "Pipeline %s: %s → %s",
                self.current_run.run_id, old_state.value, new_state.value,
            )
