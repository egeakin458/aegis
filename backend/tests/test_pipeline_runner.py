"""
Tests for the PipelineRunner state machine.

Coverage:
  1. Happy path — full RA → SA → Dev → QA → COMPLETE pipeline
  2. State transitions and event emission across the full pipeline
  3. Clarification loop — RA pauses pipeline, resume() continues it, max-round cap
  4. Code revision loop — QA revise_code → Dev reruns, max 2 cycles then partial
  5. Design revision loop — QA revise_design → SA reruns then Dev reruns, max 1 cycle
  6. Cycle cap fallback — design revision cap falls back to code revision, then partial
  7. Context passing — each agent receives exactly the right keys
  8. Failure handling — agent ValueError → FAILED state, PIPELINE_FAILED event
  9. Token accumulation — total_tokens is updated from emitted events
 10. PipelineRun fields — outcome, completed_at, feedback_cycles, state
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.base import BaseAgent
from app.pipeline.runner import PipelineRunner
from app.schemas.agent_outputs import (
    APIEndpoint,
    CodeFile,
    CodeOutput,
    DataField,
    DataModel,
    FileSpec,
    QAReview,
    ReviewVerdict,
    TechnicalDesign,
    UIComponent,
)
from app.schemas.customer_config import (
    ClarificationQuestion,
    FinalizedConfig,
)
from app.schemas.pipeline_events import (
    AgentName,
    EventType,
    PipelineEvent,
    PipelineState,
    TokenUsage,
)
from app.schemas.ra_output import RAOutput


# ===========================================================================
# Module-level helpers / factories
# ===========================================================================


def _make_clarification_ra_output(
    questions: list[ClarificationQuestion] | None = None,
) -> RAOutput:
    """Build an RAOutput that requests clarification."""
    if questions is None:
        questions = [
            ClarificationQuestion(
                id="q1",
                topic="authentication",
                original_input="Need an ordering system",
                question="Should customers log in?",
                suggestions=["Yes", "No", "Optional"],
            )
        ]
    return RAOutput(
        needs_clarification=True,
        reasoning="Need more details.",
        questions=questions,
    )


def _make_finalized_ra_output(valid_finalized_config: FinalizedConfig) -> RAOutput:
    """Build an RAOutput that finalizes the config."""
    return RAOutput(
        needs_clarification=False,
        reasoning="All clear.",
        finalized_config=valid_finalized_config,
    )


def _make_technical_design() -> TechnicalDesign:
    return TechnicalDesign(
        reasoning="Standard CRUD design.",
        project_name="cafe-ordering",
        tech_summary="Next.js 14 with App Router, Tailwind CSS, better-sqlite3",
        data_models=[
            DataModel(
                name="Order",
                description="Customer order",
                fields=[
                    DataField(name="id", type="integer"),
                    DataField(name="status", type="string"),
                ],
            )
        ],
        api_endpoints=[
            APIEndpoint(
                method="GET",
                path="/api/orders",
                description="List orders",
                response="List of orders",
            )
        ],
        ui_components=[
            UIComponent(
                name="OrderListPage",
                type="page",
                description="Displays all orders",
            )
        ],
        file_structure=[
            FileSpec(path="app/orders/page.js", purpose="Order list page")
        ],
        dependencies=["next", "tailwindcss", "better-sqlite3"],
    )


def _make_code_output() -> CodeOutput:
    return CodeOutput(
        reasoning="Implemented all features.",
        project_name="cafe-ordering",
        files=[
            CodeFile(
                path="app/orders/page.js",
                content="export default function OrderList() { return <div className='p-4'>Orders</div>; }",
                language="javascript",
                description="Order list component",
            )
        ],
        setup_instructions="npm install && npm run dev",
        features_implemented=["Order listing"],
        known_limitations=[],
    )


def _make_qa_review(verdict: ReviewVerdict = ReviewVerdict.APPROVE) -> QAReview:
    return QAReview(
        reasoning="Looks good.",
        verdict=verdict,
        issues=[],
        requirements_coverage={"Order listing": True},
        code_quality_score=4,
        summary="Code meets requirements.",
    )


def _make_mock_agent(name: AgentName, return_value: Any) -> MagicMock:
    """
    Build a mock that satisfies the BaseAgent interface expected by PipelineRunner.
    The agent's execute() immediately returns the given value without any LLM call.
    """
    agent = MagicMock(spec=BaseAgent)
    agent.execute = AsyncMock(return_value=return_value)
    return agent


def _agents_for_happy_path(valid_finalized_config: FinalizedConfig) -> dict[str, Any]:
    """Return a full agent dict wired for a clean approve run."""
    return {
        "requirements_analyst": _make_mock_agent(
            AgentName.REQUIREMENTS_ANALYST,
            _make_finalized_ra_output(valid_finalized_config),
        ),
        "solution_architect": _make_mock_agent(
            AgentName.SOLUTION_ARCHITECT,
            _make_technical_design(),
        ),
        "developer": _make_mock_agent(
            AgentName.DEVELOPER,
            _make_code_output(),
        ),
        "qa_reviewer": _make_mock_agent(
            AgentName.QA_REVIEWER,
            _make_qa_review(ReviewVerdict.APPROVE),
        ),
    }


def _event_types(events: list[PipelineEvent]) -> list[EventType]:
    return [e.event_type for e in events]


# ===========================================================================
# 1. Happy path — full pipeline to COMPLETE
# ===========================================================================


class TestHappyPath:
    """Full pipeline run that touches all 4 agents and reaches COMPLETE."""

    @pytest.mark.asyncio
    async def test_run_returns_pipeline_run_object(
        self, valid_customer_config, valid_finalized_config
    ):
        runner = PipelineRunner(agents=_agents_for_happy_path(valid_finalized_config))
        result = await runner.run(valid_customer_config)
        assert result is not None

    @pytest.mark.asyncio
    async def test_run_final_state_is_complete(
        self, valid_customer_config, valid_finalized_config
    ):
        runner = PipelineRunner(agents=_agents_for_happy_path(valid_finalized_config))
        result = await runner.run(valid_customer_config)
        assert result.state == PipelineState.COMPLETE

    @pytest.mark.asyncio
    async def test_run_outcome_is_success(
        self, valid_customer_config, valid_finalized_config
    ):
        runner = PipelineRunner(agents=_agents_for_happy_path(valid_finalized_config))
        result = await runner.run(valid_customer_config)
        assert result.outcome == "success"

    @pytest.mark.asyncio
    async def test_run_completed_at_is_set(
        self, valid_customer_config, valid_finalized_config
    ):
        runner = PipelineRunner(agents=_agents_for_happy_path(valid_finalized_config))
        result = await runner.run(valid_customer_config)
        assert result.completed_at is not None

    @pytest.mark.asyncio
    async def test_run_emits_pipeline_started_event(
        self, valid_customer_config, valid_finalized_config
    ):
        events = []
        runner = PipelineRunner(
            agents=_agents_for_happy_path(valid_finalized_config),
            emit_event=events.append,
        )
        await runner.run(valid_customer_config)
        assert EventType.PIPELINE_STARTED in _event_types(events)

    @pytest.mark.asyncio
    async def test_run_emits_pipeline_complete_event(
        self, valid_customer_config, valid_finalized_config
    ):
        events = []
        runner = PipelineRunner(
            agents=_agents_for_happy_path(valid_finalized_config),
            emit_event=events.append,
        )
        await runner.run(valid_customer_config)
        assert EventType.PIPELINE_COMPLETE in _event_types(events)

    @pytest.mark.asyncio
    async def test_run_pipeline_started_comes_before_pipeline_complete(
        self, valid_customer_config, valid_finalized_config
    ):
        events = []
        runner = PipelineRunner(
            agents=_agents_for_happy_path(valid_finalized_config),
            emit_event=events.append,
        )
        await runner.run(valid_customer_config)
        types = _event_types(events)
        assert types.index(EventType.PIPELINE_STARTED) < types.index(
            EventType.PIPELINE_COMPLETE
        )

    @pytest.mark.asyncio
    async def test_run_emits_config_finalized_event(
        self, valid_customer_config, valid_finalized_config
    ):
        events = []
        runner = PipelineRunner(
            agents=_agents_for_happy_path(valid_finalized_config),
            emit_event=events.append,
        )
        await runner.run(valid_customer_config)
        assert EventType.CONFIG_FINALIZED in _event_types(events)

    @pytest.mark.asyncio
    async def test_run_config_finalized_event_carries_project_summary(
        self, valid_customer_config, valid_finalized_config
    ):
        events = []
        runner = PipelineRunner(
            agents=_agents_for_happy_path(valid_finalized_config),
            emit_event=events.append,
        )
        await runner.run(valid_customer_config)
        cfg_event = next(
            e for e in events if e.event_type == EventType.CONFIG_FINALIZED
        )
        assert "project_summary" in cfg_event.data

    @pytest.mark.asyncio
    async def test_run_all_four_agents_are_called_once(
        self, valid_customer_config, valid_finalized_config
    ):
        agents = _agents_for_happy_path(valid_finalized_config)
        runner = PipelineRunner(agents=agents)
        await runner.run(valid_customer_config)

        agents["requirements_analyst"].execute.assert_called_once()
        agents["solution_architect"].execute.assert_called_once()
        agents["developer"].execute.assert_called_once()
        agents["qa_reviewer"].execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_pipeline_started_event_agent_is_system(
        self, valid_customer_config, valid_finalized_config
    ):
        events = []
        runner = PipelineRunner(
            agents=_agents_for_happy_path(valid_finalized_config),
            emit_event=events.append,
        )
        await runner.run(valid_customer_config)
        started = next(e for e in events if e.event_type == EventType.PIPELINE_STARTED)
        assert started.agent == AgentName.SYSTEM

    @pytest.mark.asyncio
    async def test_run_run_id_is_consistent_across_all_events(
        self, valid_customer_config, valid_finalized_config
    ):
        events = []
        runner = PipelineRunner(
            agents=_agents_for_happy_path(valid_finalized_config),
            emit_event=events.append,
        )
        result = await runner.run(valid_customer_config)
        for event in events:
            assert event.run_id == result.run_id

    @pytest.mark.asyncio
    async def test_run_events_list_on_pipeline_run_contains_all_emitted_events(
        self, valid_customer_config, valid_finalized_config
    ):
        runner = PipelineRunner(agents=_agents_for_happy_path(valid_finalized_config))
        result = await runner.run(valid_customer_config)
        # At minimum: PIPELINE_STARTED + CONFIG_FINALIZED + PIPELINE_COMPLETE
        assert len(result.events) >= 3

    @pytest.mark.asyncio
    async def test_run_no_feedback_cycles_in_clean_run(
        self, valid_customer_config, valid_finalized_config
    ):
        runner = PipelineRunner(agents=_agents_for_happy_path(valid_finalized_config))
        result = await runner.run(valid_customer_config)
        assert result.feedback_cycles["code_revisions"] == 0
        assert result.feedback_cycles["design_revisions"] == 0


# ===========================================================================
# 2. Clarification loop
# ===========================================================================


class TestClarificationLoop:
    """RA returns needs_clarification=True → pipeline pauses → resume() continues."""

    def _agents_with_clarification_then_finalize(
        self, valid_finalized_config: FinalizedConfig
    ) -> dict[str, Any]:
        """RA asks questions on the first call, finalizes on the second."""
        ra = MagicMock(spec=BaseAgent)
        ra.execute = AsyncMock(
            side_effect=[
                _make_clarification_ra_output(),
                _make_finalized_ra_output(valid_finalized_config),
            ]
        )
        return {
            "requirements_analyst": ra,
            "solution_architect": _make_mock_agent(
                AgentName.SOLUTION_ARCHITECT, _make_technical_design()
            ),
            "developer": _make_mock_agent(
                AgentName.DEVELOPER, _make_code_output()
            ),
            "qa_reviewer": _make_mock_agent(
                AgentName.QA_REVIEWER, _make_qa_review(ReviewVerdict.APPROVE)
            ),
        }

    @pytest.mark.asyncio
    async def test_clarification_run_state_is_clarification(
        self, valid_customer_config, valid_finalized_config
    ):
        ra = _make_mock_agent(
            AgentName.REQUIREMENTS_ANALYST, _make_clarification_ra_output()
        )
        runner = PipelineRunner(
            agents={
                "requirements_analyst": ra,
                "solution_architect": _make_mock_agent(
                    AgentName.SOLUTION_ARCHITECT, _make_technical_design()
                ),
                "developer": _make_mock_agent(
                    AgentName.DEVELOPER, _make_code_output()
                ),
                "qa_reviewer": _make_mock_agent(
                    AgentName.QA_REVIEWER, _make_qa_review()
                ),
            }
        )
        result = await runner.run(valid_customer_config)
        assert result.state == PipelineState.CLARIFICATION

    @pytest.mark.asyncio
    async def test_clarification_run_emits_clarification_needed_event(
        self, valid_customer_config
    ):
        events = []
        ra = _make_mock_agent(
            AgentName.REQUIREMENTS_ANALYST, _make_clarification_ra_output()
        )
        runner = PipelineRunner(
            agents={
                "requirements_analyst": ra,
                "solution_architect": _make_mock_agent(
                    AgentName.SOLUTION_ARCHITECT, _make_technical_design()
                ),
                "developer": _make_mock_agent(
                    AgentName.DEVELOPER, _make_code_output()
                ),
                "qa_reviewer": _make_mock_agent(
                    AgentName.QA_REVIEWER, _make_qa_review()
                ),
            },
            emit_event=events.append,
        )
        await runner.run(valid_customer_config)
        assert EventType.CLARIFICATION_NEEDED in _event_types(events)

    @pytest.mark.asyncio
    async def test_clarification_needed_event_contains_questions(
        self, valid_customer_config
    ):
        events = []
        ra = _make_mock_agent(
            AgentName.REQUIREMENTS_ANALYST, _make_clarification_ra_output()
        )
        runner = PipelineRunner(
            agents={
                "requirements_analyst": ra,
                "solution_architect": _make_mock_agent(
                    AgentName.SOLUTION_ARCHITECT, _make_technical_design()
                ),
                "developer": _make_mock_agent(
                    AgentName.DEVELOPER, _make_code_output()
                ),
                "qa_reviewer": _make_mock_agent(
                    AgentName.QA_REVIEWER, _make_qa_review()
                ),
            },
            emit_event=events.append,
        )
        await runner.run(valid_customer_config)
        clarif_event = next(
            e for e in events if e.event_type == EventType.CLARIFICATION_NEEDED
        )
        assert "questions" in clarif_event.data
        assert len(clarif_event.data["questions"]) == 1

    @pytest.mark.asyncio
    async def test_clarification_needed_event_carries_round_number(
        self, valid_customer_config
    ):
        events = []
        ra = _make_mock_agent(
            AgentName.REQUIREMENTS_ANALYST, _make_clarification_ra_output()
        )
        runner = PipelineRunner(
            agents={
                "requirements_analyst": ra,
                "solution_architect": _make_mock_agent(
                    AgentName.SOLUTION_ARCHITECT, _make_technical_design()
                ),
                "developer": _make_mock_agent(
                    AgentName.DEVELOPER, _make_code_output()
                ),
                "qa_reviewer": _make_mock_agent(
                    AgentName.QA_REVIEWER, _make_qa_review()
                ),
            },
            emit_event=events.append,
        )
        await runner.run(valid_customer_config)
        clarif_event = next(
            e for e in events if e.event_type == EventType.CLARIFICATION_NEEDED
        )
        assert clarif_event.data["round"] == 1

    @pytest.mark.asyncio
    async def test_clarification_run_downstream_agents_not_called(
        self, valid_customer_config
    ):
        ra = _make_mock_agent(
            AgentName.REQUIREMENTS_ANALYST, _make_clarification_ra_output()
        )
        sa = _make_mock_agent(AgentName.SOLUTION_ARCHITECT, _make_technical_design())
        dev = _make_mock_agent(AgentName.DEVELOPER, _make_code_output())
        qa = _make_mock_agent(AgentName.QA_REVIEWER, _make_qa_review())
        runner = PipelineRunner(
            agents={
                "requirements_analyst": ra,
                "solution_architect": sa,
                "developer": dev,
                "qa_reviewer": qa,
            }
        )
        await runner.run(valid_customer_config)
        sa.execute.assert_not_called()
        dev.execute.assert_not_called()
        qa.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_resume_raises_when_not_in_clarification_state(
        self, valid_customer_config, valid_finalized_config
    ):
        runner = PipelineRunner(
            agents=_agents_for_happy_path(valid_finalized_config)
        )
        # Pipeline never ran, run is None
        with pytest.raises(ValueError, match="CLARIFICATION"):
            await runner.resume(answers={"q1": "Yes"})

    @pytest.mark.asyncio
    async def test_resume_emits_clarification_received_event(
        self, valid_customer_config, valid_finalized_config
    ):
        events = []
        agents = self._agents_with_clarification_then_finalize(valid_finalized_config)
        runner = PipelineRunner(agents=agents, emit_event=events.append)
        await runner.run(valid_customer_config)
        events.clear()

        await runner.resume(answers={"q1": "Yes, always"})
        assert EventType.CLARIFICATION_RECEIVED in _event_types(events)

    @pytest.mark.asyncio
    async def test_resume_continues_to_complete(
        self, valid_customer_config, valid_finalized_config
    ):
        agents = self._agents_with_clarification_then_finalize(valid_finalized_config)
        runner = PipelineRunner(agents=agents)
        await runner.run(valid_customer_config)
        result = await runner.resume(answers={"q1": "Yes, always"})
        assert result.state == PipelineState.COMPLETE

    @pytest.mark.asyncio
    async def test_resume_records_answers_in_clarification_history(
        self, valid_customer_config, valid_finalized_config
    ):
        agents = self._agents_with_clarification_then_finalize(valid_finalized_config)
        runner = PipelineRunner(agents=agents)
        await runner.run(valid_customer_config)
        await runner.resume(answers={"q1": "Yes, always"})
        # The round that was added should now have answers recorded
        assert runner.clarification_history[0].answers == {"q1": "Yes, always"}

    @pytest.mark.asyncio
    async def test_ra_called_with_clarification_history_on_second_round(
        self, valid_customer_config, valid_finalized_config
    ):
        agents = self._agents_with_clarification_then_finalize(valid_finalized_config)
        runner = PipelineRunner(agents=agents)
        await runner.run(valid_customer_config)
        await runner.resume(answers={"q1": "Yes, always"})

        # Second call to RA must include the history in context
        second_call_context = agents["requirements_analyst"].execute.call_args_list[1][0][0]
        assert "clarification_history" in second_call_context
        assert len(second_call_context["clarification_history"]) == 1

    @pytest.mark.asyncio
    async def test_clarification_round_cap_forces_finalization(
        self, valid_customer_config, valid_finalized_config
    ):
        """After max_clarification_rounds (3) the RA is called with mode='finalize'."""
        # Build an RA that always asks for clarification — should be forced to finalize
        # on the 4th call when mode becomes 'finalize'
        clarification_output = _make_clarification_ra_output()
        finalized_output = _make_finalized_ra_output(valid_finalized_config)

        # Three clarification rounds, then one finalization
        ra = MagicMock(spec=BaseAgent)
        ra.execute = AsyncMock(
            side_effect=[
                clarification_output,  # round 1 — asks questions
                clarification_output,  # round 2 — asks questions
                clarification_output,  # round 3 — asks questions (cap hit)
                finalized_output,       # round 4 — forced finalize
            ]
        )

        runner = PipelineRunner(
            agents={
                "requirements_analyst": ra,
                "solution_architect": _make_mock_agent(
                    AgentName.SOLUTION_ARCHITECT, _make_technical_design()
                ),
                "developer": _make_mock_agent(
                    AgentName.DEVELOPER, _make_code_output()
                ),
                "qa_reviewer": _make_mock_agent(
                    AgentName.QA_REVIEWER, _make_qa_review(ReviewVerdict.APPROVE)
                ),
            }
        )

        # Round 1
        result = await runner.run(valid_customer_config)
        assert result.state == PipelineState.CLARIFICATION

        # Round 2
        result = await runner.resume(answers={"q1": "a"})
        assert result.state == PipelineState.CLARIFICATION

        # Round 3 — this is the cap (max_clarification_rounds=3)
        result = await runner.resume(answers={"q1": "b"})
        assert result.state == PipelineState.CLARIFICATION

        # Resume after cap — RA must be called with mode='finalize'
        result = await runner.resume(answers={"q1": "c"})
        assert result.state == PipelineState.COMPLETE

        # Verify the 4th call used mode='finalize'
        fourth_call_context = ra.execute.call_args_list[3][0][0]
        assert fourth_call_context.get("mode") == "finalize"


# ===========================================================================
# 3. Code revision loop
# ===========================================================================


class TestCodeRevisionLoop:
    """QA returns revise_code → Developer reruns, max 2 cycles."""

    def _agents_with_code_revisions(
        self,
        valid_finalized_config: FinalizedConfig,
        revisions_before_approve: int,
    ) -> dict[str, Any]:
        """QA returns revise_code `revisions_before_approve` times, then approve."""
        qa_side_effects = [
            _make_qa_review(ReviewVerdict.REVISE_CODE)
            for _ in range(revisions_before_approve)
        ] + [_make_qa_review(ReviewVerdict.APPROVE)]

        return {
            "requirements_analyst": _make_mock_agent(
                AgentName.REQUIREMENTS_ANALYST,
                _make_finalized_ra_output(valid_finalized_config),
            ),
            "solution_architect": _make_mock_agent(
                AgentName.SOLUTION_ARCHITECT, _make_technical_design()
            ),
            "developer": _make_mock_agent(
                AgentName.DEVELOPER, _make_code_output()
            ),
            "qa_reviewer": MagicMock(
                spec=BaseAgent,
                execute=AsyncMock(side_effect=qa_side_effects),
            ),
        }

    @pytest.mark.asyncio
    async def test_one_code_revision_reaches_complete(
        self, valid_customer_config, valid_finalized_config
    ):
        agents = self._agents_with_code_revisions(valid_finalized_config, 1)
        runner = PipelineRunner(agents=agents)
        result = await runner.run(valid_customer_config)
        assert result.state == PipelineState.COMPLETE

    @pytest.mark.asyncio
    async def test_one_code_revision_outcome_is_success(
        self, valid_customer_config, valid_finalized_config
    ):
        agents = self._agents_with_code_revisions(valid_finalized_config, 1)
        runner = PipelineRunner(agents=agents)
        result = await runner.run(valid_customer_config)
        assert result.outcome == "success"

    @pytest.mark.asyncio
    async def test_one_code_revision_developer_called_twice(
        self, valid_customer_config, valid_finalized_config
    ):
        agents = self._agents_with_code_revisions(valid_finalized_config, 1)
        runner = PipelineRunner(agents=agents)
        await runner.run(valid_customer_config)
        assert agents["developer"].execute.call_count == 2

    @pytest.mark.asyncio
    async def test_one_code_revision_feedback_cycle_counter_is_one(
        self, valid_customer_config, valid_finalized_config
    ):
        agents = self._agents_with_code_revisions(valid_finalized_config, 1)
        runner = PipelineRunner(agents=agents)
        result = await runner.run(valid_customer_config)
        assert result.feedback_cycles["code_revisions"] == 1

    @pytest.mark.asyncio
    async def test_one_code_revision_emits_revision_started_event(
        self, valid_customer_config, valid_finalized_config
    ):
        events = []
        agents = self._agents_with_code_revisions(valid_finalized_config, 1)
        runner = PipelineRunner(agents=agents, emit_event=events.append)
        await runner.run(valid_customer_config)
        assert EventType.REVISION_STARTED in _event_types(events)

    @pytest.mark.asyncio
    async def test_revision_started_event_data_has_revision_type_code(
        self, valid_customer_config, valid_finalized_config
    ):
        events = []
        agents = self._agents_with_code_revisions(valid_finalized_config, 1)
        runner = PipelineRunner(agents=agents, emit_event=events.append)
        await runner.run(valid_customer_config)
        rev_event = next(
            e for e in events if e.event_type == EventType.REVISION_STARTED
        )
        assert rev_event.data.get("revision_type") == "code"

    @pytest.mark.asyncio
    async def test_revision_context_includes_previous_code_and_qa_review(
        self, valid_customer_config, valid_finalized_config
    ):
        agents = self._agents_with_code_revisions(valid_finalized_config, 1)
        runner = PipelineRunner(agents=agents)
        await runner.run(valid_customer_config)

        # The second developer call (index 1) must have previous_code and qa_review
        second_dev_context = agents["developer"].execute.call_args_list[1][0][0]
        assert "previous_code" in second_dev_context
        assert "qa_review" in second_dev_context

    @pytest.mark.asyncio
    async def test_max_code_revisions_cap_produces_partial_outcome(
        self, valid_customer_config, valid_finalized_config
    ):
        """After 2 revisions QA still says revise_code → outcome partial, state COMPLETE."""
        qa = MagicMock(
            spec=BaseAgent,
            execute=AsyncMock(
                return_value=_make_qa_review(ReviewVerdict.REVISE_CODE)
            ),
        )
        agents = {
            "requirements_analyst": _make_mock_agent(
                AgentName.REQUIREMENTS_ANALYST,
                _make_finalized_ra_output(valid_finalized_config),
            ),
            "solution_architect": _make_mock_agent(
                AgentName.SOLUTION_ARCHITECT, _make_technical_design()
            ),
            "developer": _make_mock_agent(AgentName.DEVELOPER, _make_code_output()),
            "qa_reviewer": qa,
        }
        runner = PipelineRunner(agents=agents)
        result = await runner.run(valid_customer_config)
        assert result.state == PipelineState.COMPLETE
        assert result.outcome == "partial"

    @pytest.mark.asyncio
    async def test_max_code_revisions_developer_called_three_times(
        self, valid_customer_config, valid_finalized_config
    ):
        """Initial run + 2 revisions = 3 developer calls total."""
        dev = _make_mock_agent(AgentName.DEVELOPER, _make_code_output())
        qa = MagicMock(
            spec=BaseAgent,
            execute=AsyncMock(
                return_value=_make_qa_review(ReviewVerdict.REVISE_CODE)
            ),
        )
        agents = {
            "requirements_analyst": _make_mock_agent(
                AgentName.REQUIREMENTS_ANALYST,
                _make_finalized_ra_output(valid_finalized_config),
            ),
            "solution_architect": _make_mock_agent(
                AgentName.SOLUTION_ARCHITECT, _make_technical_design()
            ),
            "developer": dev,
            "qa_reviewer": qa,
        }
        runner = PipelineRunner(agents=agents)
        await runner.run(valid_customer_config)
        assert dev.execute.call_count == 3


# ===========================================================================
# 4. Design revision loop
# ===========================================================================


class TestDesignRevisionLoop:
    """QA returns revise_design → SA reruns, then Dev reruns."""

    def _agents_with_one_design_revision(
        self, valid_finalized_config: FinalizedConfig
    ) -> dict[str, Any]:
        qa = MagicMock(
            spec=BaseAgent,
            execute=AsyncMock(
                side_effect=[
                    _make_qa_review(ReviewVerdict.REVISE_DESIGN),
                    _make_qa_review(ReviewVerdict.APPROVE),
                ]
            ),
        )
        return {
            "requirements_analyst": _make_mock_agent(
                AgentName.REQUIREMENTS_ANALYST,
                _make_finalized_ra_output(valid_finalized_config),
            ),
            "solution_architect": _make_mock_agent(
                AgentName.SOLUTION_ARCHITECT, _make_technical_design()
            ),
            "developer": _make_mock_agent(AgentName.DEVELOPER, _make_code_output()),
            "qa_reviewer": qa,
        }

    @pytest.mark.asyncio
    async def test_one_design_revision_reaches_complete(
        self, valid_customer_config, valid_finalized_config
    ):
        agents = self._agents_with_one_design_revision(valid_finalized_config)
        runner = PipelineRunner(agents=agents)
        result = await runner.run(valid_customer_config)
        assert result.state == PipelineState.COMPLETE

    @pytest.mark.asyncio
    async def test_one_design_revision_outcome_is_success(
        self, valid_customer_config, valid_finalized_config
    ):
        agents = self._agents_with_one_design_revision(valid_finalized_config)
        runner = PipelineRunner(agents=agents)
        result = await runner.run(valid_customer_config)
        assert result.outcome == "success"

    @pytest.mark.asyncio
    async def test_one_design_revision_architect_called_twice(
        self, valid_customer_config, valid_finalized_config
    ):
        agents = self._agents_with_one_design_revision(valid_finalized_config)
        runner = PipelineRunner(agents=agents)
        await runner.run(valid_customer_config)
        assert agents["solution_architect"].execute.call_count == 2

    @pytest.mark.asyncio
    async def test_one_design_revision_developer_called_twice(
        self, valid_customer_config, valid_finalized_config
    ):
        agents = self._agents_with_one_design_revision(valid_finalized_config)
        runner = PipelineRunner(agents=agents)
        await runner.run(valid_customer_config)
        assert agents["developer"].execute.call_count == 2

    @pytest.mark.asyncio
    async def test_one_design_revision_feedback_cycle_counter_is_one(
        self, valid_customer_config, valid_finalized_config
    ):
        agents = self._agents_with_one_design_revision(valid_finalized_config)
        runner = PipelineRunner(agents=agents)
        result = await runner.run(valid_customer_config)
        assert result.feedback_cycles["design_revisions"] == 1

    @pytest.mark.asyncio
    async def test_design_revision_context_includes_previous_design_and_qa_review(
        self, valid_customer_config, valid_finalized_config
    ):
        agents = self._agents_with_one_design_revision(valid_finalized_config)
        runner = PipelineRunner(agents=agents)
        await runner.run(valid_customer_config)

        # Second SA call must have previous_design and qa_review
        second_sa_context = agents["solution_architect"].execute.call_args_list[1][0][0]
        assert "previous_design" in second_sa_context
        assert "qa_review" in second_sa_context

    @pytest.mark.asyncio
    async def test_design_revision_emits_revision_started_event_with_type_design(
        self, valid_customer_config, valid_finalized_config
    ):
        events = []
        agents = self._agents_with_one_design_revision(valid_finalized_config)
        runner = PipelineRunner(agents=agents, emit_event=events.append)
        await runner.run(valid_customer_config)
        design_rev_events = [
            e
            for e in events
            if e.event_type == EventType.REVISION_STARTED
            and e.data.get("revision_type") == "design"
        ]
        assert len(design_rev_events) == 1


# ===========================================================================
# 5. Design revision cap fallback
# ===========================================================================


class TestDesignRevisionCapFallback:
    """When design revision cap (1) is hit, falls back to code revision or partial."""

    @pytest.mark.asyncio
    async def test_design_revision_cap_falls_back_to_code_revision(
        self, valid_customer_config, valid_finalized_config
    ):
        """
        QA always says revise_design. After 1 design revision (cap), runner must
        fall back to code revision path since code_revision_count < max.
        Then it tries another code revision. Because QA still says revise_design
        and the design cap is already hit, code revision cap is tested separately.
        For this test: after design cap, next QA call approves → success.
        """
        qa = MagicMock(
            spec=BaseAgent,
            execute=AsyncMock(
                side_effect=[
                    _make_qa_review(ReviewVerdict.REVISE_DESIGN),  # triggers design revision
                    _make_qa_review(ReviewVerdict.REVISE_DESIGN),  # cap hit → code revision path
                    _make_qa_review(ReviewVerdict.APPROVE),         # approves
                ]
            ),
        )
        agents = {
            "requirements_analyst": _make_mock_agent(
                AgentName.REQUIREMENTS_ANALYST,
                _make_finalized_ra_output(valid_finalized_config),
            ),
            "solution_architect": _make_mock_agent(
                AgentName.SOLUTION_ARCHITECT, _make_technical_design()
            ),
            "developer": _make_mock_agent(AgentName.DEVELOPER, _make_code_output()),
            "qa_reviewer": qa,
        }
        runner = PipelineRunner(agents=agents)
        result = await runner.run(valid_customer_config)
        assert result.state == PipelineState.COMPLETE

    @pytest.mark.asyncio
    async def test_design_revision_cap_and_code_revision_cap_both_hit_gives_partial(
        self, valid_customer_config, valid_finalized_config
    ):
        """
        QA always says revise_design. After design cap AND code revision cap are
        both exhausted, the outcome must be partial.
        Design cap = 1, code cap = 2.
        QA calls: revise_design (design cycle 1) → revise_design (code cycle 1, design cap hit)
        → revise_design (code cycle 2) → cap hit → partial
        """
        qa = MagicMock(
            spec=BaseAgent,
            execute=AsyncMock(
                return_value=_make_qa_review(ReviewVerdict.REVISE_DESIGN)
            ),
        )
        agents = {
            "requirements_analyst": _make_mock_agent(
                AgentName.REQUIREMENTS_ANALYST,
                _make_finalized_ra_output(valid_finalized_config),
            ),
            "solution_architect": _make_mock_agent(
                AgentName.SOLUTION_ARCHITECT, _make_technical_design()
            ),
            "developer": _make_mock_agent(AgentName.DEVELOPER, _make_code_output()),
            "qa_reviewer": qa,
        }
        runner = PipelineRunner(agents=agents)
        result = await runner.run(valid_customer_config)
        assert result.outcome == "partial"
        assert result.state == PipelineState.COMPLETE


# ===========================================================================
# 6. Context passing
# ===========================================================================


class TestContextPassing:
    """Each agent must receive exactly the right keys in its context dict."""

    @pytest.mark.asyncio
    async def test_sa_receives_finalized_config(
        self, valid_customer_config, valid_finalized_config
    ):
        agents = _agents_for_happy_path(valid_finalized_config)
        runner = PipelineRunner(agents=agents)
        await runner.run(valid_customer_config)

        sa_context = agents["solution_architect"].execute.call_args[0][0]
        assert "finalized_config" in sa_context
        assert sa_context["finalized_config"] is valid_finalized_config

    @pytest.mark.asyncio
    async def test_sa_context_does_not_include_customer_config_directly(
        self, valid_customer_config, valid_finalized_config
    ):
        """SA only gets finalized_config, not raw customer_config."""
        agents = _agents_for_happy_path(valid_finalized_config)
        runner = PipelineRunner(agents=agents)
        await runner.run(valid_customer_config)

        sa_context = agents["solution_architect"].execute.call_args[0][0]
        # SA context should only have finalized_config
        assert set(sa_context.keys()) == {"finalized_config"}

    @pytest.mark.asyncio
    async def test_dev_receives_finalized_config_and_technical_design(
        self, valid_customer_config, valid_finalized_config
    ):
        agents = _agents_for_happy_path(valid_finalized_config)
        runner = PipelineRunner(agents=agents)
        await runner.run(valid_customer_config)

        dev_context = agents["developer"].execute.call_args[0][0]
        assert "finalized_config" in dev_context
        assert "technical_design" in dev_context

    @pytest.mark.asyncio
    async def test_dev_context_does_not_include_previous_code_on_first_run(
        self, valid_customer_config, valid_finalized_config
    ):
        agents = _agents_for_happy_path(valid_finalized_config)
        runner = PipelineRunner(agents=agents)
        await runner.run(valid_customer_config)

        dev_context = agents["developer"].execute.call_args[0][0]
        assert "previous_code" not in dev_context
        assert "qa_review" not in dev_context

    @pytest.mark.asyncio
    async def test_qa_receives_finalized_config_technical_design_and_code_output(
        self, valid_customer_config, valid_finalized_config
    ):
        agents = _agents_for_happy_path(valid_finalized_config)
        runner = PipelineRunner(agents=agents)
        await runner.run(valid_customer_config)

        qa_context = agents["qa_reviewer"].execute.call_args[0][0]
        assert "finalized_config" in qa_context
        assert "technical_design" in qa_context
        assert "code_output" in qa_context

    @pytest.mark.asyncio
    async def test_ra_receives_customer_config(
        self, valid_customer_config, valid_finalized_config
    ):
        agents = _agents_for_happy_path(valid_finalized_config)
        runner = PipelineRunner(agents=agents)
        await runner.run(valid_customer_config)

        ra_context = agents["requirements_analyst"].execute.call_args[0][0]
        assert "customer_config" in ra_context
        assert ra_context["customer_config"] is valid_customer_config

    @pytest.mark.asyncio
    async def test_ra_receives_mode_key(
        self, valid_customer_config, valid_finalized_config
    ):
        agents = _agents_for_happy_path(valid_finalized_config)
        runner = PipelineRunner(agents=agents)
        await runner.run(valid_customer_config)

        ra_context = agents["requirements_analyst"].execute.call_args[0][0]
        assert "mode" in ra_context

    @pytest.mark.asyncio
    async def test_ra_receives_mode_analyze_on_first_run(
        self, valid_customer_config, valid_finalized_config
    ):
        agents = _agents_for_happy_path(valid_finalized_config)
        runner = PipelineRunner(agents=agents)
        await runner.run(valid_customer_config)

        ra_context = agents["requirements_analyst"].execute.call_args[0][0]
        assert ra_context["mode"] == "analyze"

    @pytest.mark.asyncio
    async def test_code_revision_context_has_previous_code_pointing_to_first_output(
        self, valid_customer_config, valid_finalized_config
    ):
        first_code = _make_code_output()
        first_code.reasoning = "First implementation."
        second_code = _make_code_output()
        second_code.reasoning = "Revised implementation."

        dev = MagicMock(
            spec=BaseAgent,
            execute=AsyncMock(side_effect=[first_code, second_code]),
        )
        qa = MagicMock(
            spec=BaseAgent,
            execute=AsyncMock(
                side_effect=[
                    _make_qa_review(ReviewVerdict.REVISE_CODE),
                    _make_qa_review(ReviewVerdict.APPROVE),
                ]
            ),
        )
        agents = {
            "requirements_analyst": _make_mock_agent(
                AgentName.REQUIREMENTS_ANALYST,
                _make_finalized_ra_output(valid_finalized_config),
            ),
            "solution_architect": _make_mock_agent(
                AgentName.SOLUTION_ARCHITECT, _make_technical_design()
            ),
            "developer": dev,
            "qa_reviewer": qa,
        }
        runner = PipelineRunner(agents=agents)
        await runner.run(valid_customer_config)

        second_dev_context = dev.execute.call_args_list[1][0][0]
        # previous_code should be the first CodeOutput instance
        assert second_dev_context["previous_code"] is first_code


# ===========================================================================
# 7. Failure handling
# ===========================================================================


class TestFailureHandling:
    """Agent raises ValueError → FAILED state and PIPELINE_FAILED event."""

    @pytest.mark.asyncio
    async def test_ra_failure_sets_state_to_failed(self, valid_customer_config):
        ra = MagicMock(spec=BaseAgent)
        ra.execute = AsyncMock(
            side_effect=ValueError("RA failed output validation after retry: bad schema")
        )
        runner = PipelineRunner(
            agents={
                "requirements_analyst": ra,
                "solution_architect": _make_mock_agent(
                    AgentName.SOLUTION_ARCHITECT, _make_technical_design()
                ),
                "developer": _make_mock_agent(AgentName.DEVELOPER, _make_code_output()),
                "qa_reviewer": _make_mock_agent(
                    AgentName.QA_REVIEWER, _make_qa_review()
                ),
            }
        )
        result = await runner.run(valid_customer_config)
        assert result.state == PipelineState.FAILED

    @pytest.mark.asyncio
    async def test_ra_failure_sets_outcome_to_failed(self, valid_customer_config):
        ra = MagicMock(spec=BaseAgent)
        ra.execute = AsyncMock(side_effect=ValueError("RA failed"))
        runner = PipelineRunner(
            agents={
                "requirements_analyst": ra,
                "solution_architect": _make_mock_agent(
                    AgentName.SOLUTION_ARCHITECT, _make_technical_design()
                ),
                "developer": _make_mock_agent(AgentName.DEVELOPER, _make_code_output()),
                "qa_reviewer": _make_mock_agent(
                    AgentName.QA_REVIEWER, _make_qa_review()
                ),
            }
        )
        result = await runner.run(valid_customer_config)
        assert result.outcome == "failed"

    @pytest.mark.asyncio
    async def test_ra_failure_emits_pipeline_failed_event(self, valid_customer_config):
        events = []
        ra = MagicMock(spec=BaseAgent)
        ra.execute = AsyncMock(side_effect=ValueError("RA failed"))
        runner = PipelineRunner(
            agents={
                "requirements_analyst": ra,
                "solution_architect": _make_mock_agent(
                    AgentName.SOLUTION_ARCHITECT, _make_technical_design()
                ),
                "developer": _make_mock_agent(AgentName.DEVELOPER, _make_code_output()),
                "qa_reviewer": _make_mock_agent(
                    AgentName.QA_REVIEWER, _make_qa_review()
                ),
            },
            emit_event=events.append,
        )
        await runner.run(valid_customer_config)
        assert EventType.PIPELINE_FAILED in _event_types(events)

    @pytest.mark.asyncio
    async def test_pipeline_failed_event_contains_error_message(
        self, valid_customer_config
    ):
        events = []
        ra = MagicMock(spec=BaseAgent)
        ra.execute = AsyncMock(side_effect=ValueError("Descriptive error message"))
        runner = PipelineRunner(
            agents={
                "requirements_analyst": ra,
                "solution_architect": _make_mock_agent(
                    AgentName.SOLUTION_ARCHITECT, _make_technical_design()
                ),
                "developer": _make_mock_agent(AgentName.DEVELOPER, _make_code_output()),
                "qa_reviewer": _make_mock_agent(
                    AgentName.QA_REVIEWER, _make_qa_review()
                ),
            },
            emit_event=events.append,
        )
        await runner.run(valid_customer_config)
        failed_event = next(
            e for e in events if e.event_type == EventType.PIPELINE_FAILED
        )
        assert "Descriptive error message" in failed_event.data.get("error", "")

    @pytest.mark.asyncio
    async def test_sa_failure_sets_state_to_failed(
        self, valid_customer_config, valid_finalized_config
    ):
        sa = MagicMock(spec=BaseAgent)
        sa.execute = AsyncMock(side_effect=ValueError("SA crashed"))
        runner = PipelineRunner(
            agents={
                "requirements_analyst": _make_mock_agent(
                    AgentName.REQUIREMENTS_ANALYST,
                    _make_finalized_ra_output(valid_finalized_config),
                ),
                "solution_architect": sa,
                "developer": _make_mock_agent(AgentName.DEVELOPER, _make_code_output()),
                "qa_reviewer": _make_mock_agent(
                    AgentName.QA_REVIEWER, _make_qa_review()
                ),
            }
        )
        result = await runner.run(valid_customer_config)
        assert result.state == PipelineState.FAILED

    @pytest.mark.asyncio
    async def test_dev_failure_downstream_agents_not_called(
        self, valid_customer_config, valid_finalized_config
    ):
        qa = _make_mock_agent(AgentName.QA_REVIEWER, _make_qa_review())
        dev = MagicMock(spec=BaseAgent)
        dev.execute = AsyncMock(side_effect=ValueError("Dev crashed"))
        runner = PipelineRunner(
            agents={
                "requirements_analyst": _make_mock_agent(
                    AgentName.REQUIREMENTS_ANALYST,
                    _make_finalized_ra_output(valid_finalized_config),
                ),
                "solution_architect": _make_mock_agent(
                    AgentName.SOLUTION_ARCHITECT, _make_technical_design()
                ),
                "developer": dev,
                "qa_reviewer": qa,
            }
        )
        await runner.run(valid_customer_config)
        qa.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_failure_sets_completed_at(self, valid_customer_config):
        ra = MagicMock(spec=BaseAgent)
        ra.execute = AsyncMock(side_effect=ValueError("crash"))
        runner = PipelineRunner(
            agents={
                "requirements_analyst": ra,
                "solution_architect": _make_mock_agent(
                    AgentName.SOLUTION_ARCHITECT, _make_technical_design()
                ),
                "developer": _make_mock_agent(AgentName.DEVELOPER, _make_code_output()),
                "qa_reviewer": _make_mock_agent(
                    AgentName.QA_REVIEWER, _make_qa_review()
                ),
            }
        )
        result = await runner.run(valid_customer_config)
        assert result.completed_at is not None

    @pytest.mark.asyncio
    async def test_pipeline_failed_event_agent_is_system(self, valid_customer_config):
        events = []
        ra = MagicMock(spec=BaseAgent)
        ra.execute = AsyncMock(side_effect=ValueError("crash"))
        runner = PipelineRunner(
            agents={
                "requirements_analyst": ra,
                "solution_architect": _make_mock_agent(
                    AgentName.SOLUTION_ARCHITECT, _make_technical_design()
                ),
                "developer": _make_mock_agent(AgentName.DEVELOPER, _make_code_output()),
                "qa_reviewer": _make_mock_agent(
                    AgentName.QA_REVIEWER, _make_qa_review()
                ),
            },
            emit_event=events.append,
        )
        await runner.run(valid_customer_config)
        failed_event = next(
            e for e in events if e.event_type == EventType.PIPELINE_FAILED
        )
        assert failed_event.agent == AgentName.SYSTEM


# ===========================================================================
# 8. Token accumulation
# ===========================================================================


class TestTokenAccumulation:
    """
    PipelineRunner.emit_event() must accumulate tokens from all events
    into run.total_tokens.
    """

    @pytest.mark.asyncio
    async def test_total_tokens_accumulate_from_emitted_events(
        self, valid_customer_config, valid_finalized_config
    ):
        """
        Manually emit events with known token counts via runner.emit_event()
        and verify total_tokens reflects the sum.
        """
        runner = PipelineRunner(
            agents=_agents_for_happy_path(valid_finalized_config)
        )
        # Initialise the run object
        await runner.run(valid_customer_config)
        # We'll start a fresh run to check accumulation from zero
        from app.schemas.pipeline_events import PipelineRun

        runner.current_run = PipelineRun()
        runner.emit_event(
            PipelineEvent(
                run_id=runner.current_run.run_id,
                agent=AgentName.REQUIREMENTS_ANALYST,
                event_type=EventType.AGENT_COMPLETE,
                message="Done.",
                tokens_used=TokenUsage(input_tokens=100, output_tokens=50),
            )
        )
        runner.emit_event(
            PipelineEvent(
                run_id=runner.current_run.run_id,
                agent=AgentName.SOLUTION_ARCHITECT,
                event_type=EventType.AGENT_COMPLETE,
                message="Done.",
                tokens_used=TokenUsage(input_tokens=200, output_tokens=80),
            )
        )
        assert runner.current_run.total_tokens.input_tokens == 300
        assert runner.current_run.total_tokens.output_tokens == 130

    @pytest.mark.asyncio
    async def test_events_without_tokens_do_not_crash_accumulation(
        self, valid_customer_config, valid_finalized_config
    ):
        """Events with tokens_used=None should not affect total_tokens."""
        runner = PipelineRunner(
            agents=_agents_for_happy_path(valid_finalized_config)
        )
        from app.schemas.pipeline_events import PipelineRun

        runner.current_run = PipelineRun()
        runner.emit_event(
            PipelineEvent(
                run_id=runner.current_run.run_id,
                agent=AgentName.SYSTEM,
                event_type=EventType.PIPELINE_STARTED,
                message="Starting.",
                tokens_used=None,
            )
        )
        assert runner.current_run.total_tokens.input_tokens == 0
        assert runner.current_run.total_tokens.output_tokens == 0


# ===========================================================================
# 9. PipelineRunner initialisation and edge cases
# ===========================================================================


class TestPipelineRunnerInit:
    """Structural / edge-case tests for the runner itself."""

    def test_runner_default_emit_is_noop(self, valid_finalized_config):
        """No emit_event provided should not crash."""
        runner = PipelineRunner(
            agents=_agents_for_happy_path(valid_finalized_config)
        )
        # Calling emit_event without a run should be a no-op
        event = PipelineEvent(
            run_id="test-id",
            agent=AgentName.SYSTEM,
            event_type=EventType.PIPELINE_STARTED,
            message="hi",
        )
        runner._emit(event)  # must not raise

    @pytest.mark.asyncio
    async def test_run_initialises_counters_to_zero(
        self, valid_customer_config, valid_finalized_config
    ):
        runner = PipelineRunner(agents=_agents_for_happy_path(valid_finalized_config))
        await runner.run(valid_customer_config)
        # After a clean run counters should be 0
        assert runner.code_revision_count == 0
        assert runner.design_revision_count == 0

    @pytest.mark.asyncio
    async def test_second_run_resets_counters_from_previous_run(
        self, valid_customer_config, valid_finalized_config
    ):
        """Calling run() a second time must reset all state."""
        # First run with a revision
        qa = MagicMock(
            spec=BaseAgent,
            execute=AsyncMock(
                side_effect=[
                    _make_qa_review(ReviewVerdict.REVISE_CODE),
                    _make_qa_review(ReviewVerdict.APPROVE),
                ]
            ),
        )
        agents = {
            "requirements_analyst": _make_mock_agent(
                AgentName.REQUIREMENTS_ANALYST,
                _make_finalized_ra_output(valid_finalized_config),
            ),
            "solution_architect": _make_mock_agent(
                AgentName.SOLUTION_ARCHITECT, _make_technical_design()
            ),
            "developer": _make_mock_agent(AgentName.DEVELOPER, _make_code_output()),
            "qa_reviewer": qa,
        }
        runner = PipelineRunner(agents=agents)
        await runner.run(valid_customer_config)
        assert runner.code_revision_count == 1

        # Second run — swap out QA to approve directly, reset side_effect
        agents["qa_reviewer"] = _make_mock_agent(
            AgentName.QA_REVIEWER, _make_qa_review(ReviewVerdict.APPROVE)
        )
        runner.agents = agents
        await runner.run(valid_customer_config)
        assert runner.code_revision_count == 0

    @pytest.mark.asyncio
    async def test_emit_event_adds_event_to_run_events_list(
        self, valid_customer_config, valid_finalized_config
    ):
        runner = PipelineRunner(agents=_agents_for_happy_path(valid_finalized_config))
        result = await runner.run(valid_customer_config)
        # Every event emitted during run must be in result.events
        assert len(result.events) > 0

    @pytest.mark.asyncio
    async def test_emit_event_stamps_pipeline_state_on_each_event(
        self, valid_customer_config, valid_finalized_config
    ):
        """Every event in the run's event list must have pipeline_state set."""
        runner = PipelineRunner(agents=_agents_for_happy_path(valid_finalized_config))
        result = await runner.run(valid_customer_config)
        for event in result.events:
            assert event.pipeline_state is not None

    @pytest.mark.asyncio
    async def test_resume_raises_when_run_is_none(self):
        runner = PipelineRunner(agents={})
        with pytest.raises(ValueError, match="CLARIFICATION"):
            await runner.resume(answers={})

    @pytest.mark.asyncio
    async def test_resume_raises_when_state_is_complete(
        self, valid_customer_config, valid_finalized_config
    ):
        runner = PipelineRunner(agents=_agents_for_happy_path(valid_finalized_config))
        await runner.run(valid_customer_config)
        # run is now COMPLETE, not CLARIFICATION
        with pytest.raises(ValueError, match="CLARIFICATION"):
            await runner.resume(answers={})
