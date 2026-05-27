"""
Tests for the PipelineRunner state machine (DDC mode).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.base import BaseAgent
from app.pipeline.runner import PipelineRunner
from app.schemas.agent_outputs import (
    BuildCheckResult,
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
from app.schemas.pipeline_events import (
    AgentName,
    EventType,
    PipelineEvent,
    PipelineRun,
    PipelineState,
    TokenUsage,
)
from app.schemas.ra_output import RAOutputDDC


# ===========================================================================
# Module-level autouse fixture — mock build checker to pass by default
# ===========================================================================


@pytest.fixture(autouse=True)
def mock_build_check_pass():
    """Patch run_build_check to return a passing result for all runner tests."""
    passing = BuildCheckResult(passed=True, duration_ms=5, files_checked=3)
    with patch("app.pipeline.runner.run_build_check", new=AsyncMock(return_value=passing)):
        yield


# ===========================================================================
# Module-level helpers / factories
# ===========================================================================


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
        features_implemented=[
            {"feature_id": "feat_order-listing_a1b2c3", "description": "Order listing", "implementation_notes": None}
        ],
        known_limitations=[],
    )


def _make_qa_review(verdict: ReviewVerdict = ReviewVerdict.APPROVE) -> QAReview:
    return QAReview(
        reasoning="Looks good.",
        verdict=verdict,
        issues=[],
        requirements_coverage=[
            {"feature_id": "feat_order-listing_a1b2c3", "implemented": True, "evidence": "Order list page implemented"}
        ],
        code_quality_score=4,
        summary="Code meets requirements.",
    )


def _make_mock_agent(name: AgentName, return_value: Any) -> MagicMock:
    """Build a mock that satisfies the BaseAgent interface."""
    agent = MagicMock(spec=BaseAgent)
    agent.execute = AsyncMock(return_value=return_value)
    return agent


def _agents_for_ddc_happy_path(ddc) -> dict[str, Any]:
    """Return a full agent dict wired for a clean DDC approve run."""
    ra_result = RAOutputDDC(
        needs_clarification=False,
        reasoning="DDC validated and complete.",
        finalized_config=ddc,
    )
    return {
        "requirements_analyst": _make_mock_agent(AgentName.REQUIREMENTS_ANALYST, ra_result),
        "solution_architect": _make_mock_agent(AgentName.SOLUTION_ARCHITECT, _make_technical_design()),
        "developer": _make_mock_agent(AgentName.DEVELOPER, _make_code_output()),
        "qa_reviewer": _make_mock_agent(AgentName.QA_REVIEWER, _make_qa_review(ReviewVerdict.APPROVE)),
    }


def _event_types(events: list[PipelineEvent]) -> list[EventType]:
    return [e.event_type for e in events]


# ===========================================================================
# Handler registry — every runnable state has a registered handler
# ===========================================================================


class TestHandlerRegistry:
    """Verify the state → handler registry is complete and raises on unknown states."""

    def test_every_runnable_state_has_handler(self, ddc_ecommerce):
        runner = PipelineRunner(agents=_agents_for_ddc_happy_path(ddc_ecommerce))
        non_runnable = {
            PipelineState.INTAKE,
            PipelineState.CLARIFICATION,
            PipelineState.COMPLETE,
            PipelineState.FAILED,
        }
        runnable = set(PipelineState) - non_runnable
        assert runnable == set(runner._state_handlers.keys())

    @pytest.mark.asyncio
    async def test_unknown_state_raises(self, ddc_ecommerce):
        runner = PipelineRunner(agents=_agents_for_ddc_happy_path(ddc_ecommerce))
        runner.current_run = MagicMock()
        runner.current_run.state = PipelineState.INTAKE
        runner._state_handlers.clear()
        with pytest.raises(ValueError, match="No handler registered for state"):
            await runner._run_from_state(PipelineState.REQUIREMENTS)


# ===========================================================================
# Failure handling — agent ValueError → FAILED state and PIPELINE_FAILED event
# ===========================================================================


class TestFailureHandling:
    """Agent raises ValueError → FAILED state and PIPELINE_FAILED event."""

    @pytest.mark.asyncio
    async def test_ra_failure_sets_state_to_failed(self, ddc_ecommerce):
        ra = MagicMock(spec=BaseAgent)
        ra.execute = AsyncMock(side_effect=ValueError("RA failed output validation"))
        runner = PipelineRunner(
            agents={
                "requirements_analyst": ra,
                "solution_architect": _make_mock_agent(AgentName.SOLUTION_ARCHITECT, _make_technical_design()),
                "developer": _make_mock_agent(AgentName.DEVELOPER, _make_code_output()),
                "qa_reviewer": _make_mock_agent(AgentName.QA_REVIEWER, _make_qa_review()),
            }
        )
        result = await runner.run(ddc_ecommerce)
        assert result.state == PipelineState.FAILED

    @pytest.mark.asyncio
    async def test_ra_failure_sets_outcome_to_failed(self, ddc_ecommerce):
        ra = MagicMock(spec=BaseAgent)
        ra.execute = AsyncMock(side_effect=ValueError("RA failed"))
        runner = PipelineRunner(
            agents={
                "requirements_analyst": ra,
                "solution_architect": _make_mock_agent(AgentName.SOLUTION_ARCHITECT, _make_technical_design()),
                "developer": _make_mock_agent(AgentName.DEVELOPER, _make_code_output()),
                "qa_reviewer": _make_mock_agent(AgentName.QA_REVIEWER, _make_qa_review()),
            }
        )
        result = await runner.run(ddc_ecommerce)
        assert result.outcome == "failed"

    @pytest.mark.asyncio
    async def test_ra_failure_emits_pipeline_failed_event(self, ddc_ecommerce):
        events: list[PipelineEvent] = []
        ra = MagicMock(spec=BaseAgent)
        ra.execute = AsyncMock(side_effect=ValueError("RA failed"))
        runner = PipelineRunner(
            agents={
                "requirements_analyst": ra,
                "solution_architect": _make_mock_agent(AgentName.SOLUTION_ARCHITECT, _make_technical_design()),
                "developer": _make_mock_agent(AgentName.DEVELOPER, _make_code_output()),
                "qa_reviewer": _make_mock_agent(AgentName.QA_REVIEWER, _make_qa_review()),
            },
            emit_event=events.append,
        )
        await runner.run(ddc_ecommerce)
        assert EventType.PIPELINE_FAILED in _event_types(events)

    @pytest.mark.asyncio
    async def test_pipeline_failed_event_contains_error_message(self, ddc_ecommerce):
        events: list[PipelineEvent] = []
        ra = MagicMock(spec=BaseAgent)
        ra.execute = AsyncMock(side_effect=ValueError("Descriptive error message"))
        runner = PipelineRunner(
            agents={
                "requirements_analyst": ra,
                "solution_architect": _make_mock_agent(AgentName.SOLUTION_ARCHITECT, _make_technical_design()),
                "developer": _make_mock_agent(AgentName.DEVELOPER, _make_code_output()),
                "qa_reviewer": _make_mock_agent(AgentName.QA_REVIEWER, _make_qa_review()),
            },
            emit_event=events.append,
        )
        await runner.run(ddc_ecommerce)
        failed_event = next(e for e in events if e.event_type == EventType.PIPELINE_FAILED)
        assert "Descriptive error message" in failed_event.data.get("error", "")

    @pytest.mark.asyncio
    async def test_failure_sets_completed_at(self, ddc_ecommerce):
        ra = MagicMock(spec=BaseAgent)
        ra.execute = AsyncMock(side_effect=ValueError("crash"))
        runner = PipelineRunner(
            agents={
                "requirements_analyst": ra,
                "solution_architect": _make_mock_agent(AgentName.SOLUTION_ARCHITECT, _make_technical_design()),
                "developer": _make_mock_agent(AgentName.DEVELOPER, _make_code_output()),
                "qa_reviewer": _make_mock_agent(AgentName.QA_REVIEWER, _make_qa_review()),
            }
        )
        result = await runner.run(ddc_ecommerce)
        assert result.completed_at is not None

    @pytest.mark.asyncio
    async def test_pipeline_failed_event_agent_is_system(self, ddc_ecommerce):
        events: list[PipelineEvent] = []
        ra = MagicMock(spec=BaseAgent)
        ra.execute = AsyncMock(side_effect=ValueError("crash"))
        runner = PipelineRunner(
            agents={
                "requirements_analyst": ra,
                "solution_architect": _make_mock_agent(AgentName.SOLUTION_ARCHITECT, _make_technical_design()),
                "developer": _make_mock_agent(AgentName.DEVELOPER, _make_code_output()),
                "qa_reviewer": _make_mock_agent(AgentName.QA_REVIEWER, _make_qa_review()),
            },
            emit_event=events.append,
        )
        await runner.run(ddc_ecommerce)
        failed_event = next(e for e in events if e.event_type == EventType.PIPELINE_FAILED)
        assert failed_event.agent == AgentName.SYSTEM


# ===========================================================================
# Token accumulation
# ===========================================================================


class TestTokenAccumulation:
    """PipelineRunner.emit_event() must accumulate tokens into run.total_tokens."""

    def test_total_tokens_accumulate_from_emitted_events(self, ddc_ecommerce):
        runner = PipelineRunner(agents=_agents_for_ddc_happy_path(ddc_ecommerce))
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

    def test_events_without_tokens_do_not_crash_accumulation(self, ddc_ecommerce):
        runner = PipelineRunner(agents=_agents_for_ddc_happy_path(ddc_ecommerce))
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
# DDC pipeline end-to-end
# ===========================================================================


@pytest.mark.asyncio
class TestDDCPipeline:
    """DDC mode end-to-end runner tests."""

    def _make_runner(self, agents: dict, events: list) -> PipelineRunner:
        return PipelineRunner(agents=agents, emit_event=events.append)

    async def test_ddc_pipeline_reaches_complete(self, ddc_ecommerce):
        events: list[PipelineEvent] = []
        agents = _agents_for_ddc_happy_path(ddc_ecommerce)
        runner = self._make_runner(agents, events)
        result = await runner.run(ddc_ecommerce)
        assert result.state == PipelineState.COMPLETE
        assert result.outcome == "success"

    async def test_ddc_pipeline_emits_config_finalized_event(self, ddc_ecommerce):
        events: list[PipelineEvent] = []
        agents = _agents_for_ddc_happy_path(ddc_ecommerce)
        runner = self._make_runner(agents, events)
        await runner.run(ddc_ecommerce)
        event_types = [e.event_type for e in events]
        assert EventType.CONFIG_FINALIZED in event_types

    async def test_ddc_config_finalized_event_uses_domain_description(self, ddc_ecommerce):
        events: list[PipelineEvent] = []
        agents = _agents_for_ddc_happy_path(ddc_ecommerce)
        runner = self._make_runner(agents, events)
        await runner.run(ddc_ecommerce)
        config_finalized = next(e for e in events if e.event_type == EventType.CONFIG_FINALIZED)
        assert config_finalized.data["project_summary"] == ddc_ecommerce.context.domain_description

    async def test_ddc_context_has_customer_config_v2_not_finalized_config(self, ddc_ecommerce):
        events: list[PipelineEvent] = []
        agents = _agents_for_ddc_happy_path(ddc_ecommerce)
        runner = self._make_runner(agents, events)
        await runner.run(ddc_ecommerce)
        assert "customer_config_v2" in runner.context
        assert "finalized_config" not in runner.context

    async def test_ddc_sa_receives_customer_config_v2(self, ddc_ecommerce):
        events: list[PipelineEvent] = []
        agents = _agents_for_ddc_happy_path(ddc_ecommerce)
        runner = self._make_runner(agents, events)
        await runner.run(ddc_ecommerce)
        sa_context = agents["solution_architect"].execute.call_args[0][0]
        assert "customer_config_v2" in sa_context
        assert "finalized_config" not in sa_context

    async def test_ddc_dev_receives_customer_config_v2_and_technical_design(self, ddc_ecommerce):
        events: list[PipelineEvent] = []
        agents = _agents_for_ddc_happy_path(ddc_ecommerce)
        runner = self._make_runner(agents, events)
        await runner.run(ddc_ecommerce)
        dev_context = agents["developer"].execute.call_args[0][0]
        assert "customer_config_v2" in dev_context
        assert "technical_design" in dev_context
        assert "finalized_config" not in dev_context

    async def test_ddc_qa_receives_customer_config_v2_technical_design_and_code_output(self, ddc_ecommerce):
        events: list[PipelineEvent] = []
        agents = _agents_for_ddc_happy_path(ddc_ecommerce)
        runner = self._make_runner(agents, events)
        await runner.run(ddc_ecommerce)
        qa_context = agents["qa_reviewer"].execute.call_args[0][0]
        assert "customer_config_v2" in qa_context
        assert "technical_design" in qa_context
        assert "code_output" in qa_context
        assert "finalized_config" not in qa_context

    async def test_ddc_qa_receives_build_check_result(self, ddc_ecommerce):
        events: list[PipelineEvent] = []
        agents = _agents_for_ddc_happy_path(ddc_ecommerce)
        runner = self._make_runner(agents, events)
        await runner.run(ddc_ecommerce)
        qa_context = agents["qa_reviewer"].execute.call_args[0][0]
        assert "build_check_result" in qa_context
        assert qa_context["build_check_result"] is not None
        assert qa_context["build_check_result"].passed is True

    async def test_qa_review_complete_fires_on_approve(self, ddc_ecommerce):
        """Approve path must emit a QA_REVIEW_COMPLETE event with verdict + score (Backlog #8)."""
        events: list[PipelineEvent] = []
        agents = _agents_for_ddc_happy_path(ddc_ecommerce)
        runner = self._make_runner(agents, events)
        await runner.run(ddc_ecommerce)
        qa_events = [e for e in events if e.event_type == EventType.QA_REVIEW_COMPLETE]
        assert len(qa_events) == 1, f"expected exactly one QA_REVIEW_COMPLETE, got {len(qa_events)}"
        d = qa_events[0].data
        assert d["verdict"] == "approve"
        assert d["code_quality_score"] == 4
        assert "summary" in d
        assert isinstance(d["issues"], list)
        assert isinstance(d["requirements_coverage"], list)

    async def test_qa_review_complete_fires_on_revise_code(self, ddc_ecommerce):
        """Revise paths must also emit QA_REVIEW_COMPLETE, alongside REVISION_REQUESTED."""
        events: list[PipelineEvent] = []
        agents = _agents_for_ddc_happy_path(ddc_ecommerce)
        # QA: first verdict revise_code, then approve after Developer revises.
        agents["qa_reviewer"].execute = AsyncMock(
            side_effect=[
                _make_qa_review(ReviewVerdict.REVISE_CODE),
                _make_qa_review(ReviewVerdict.APPROVE),
            ]
        )
        runner = self._make_runner(agents, events)
        await runner.run(ddc_ecommerce)
        qa_events = [e for e in events if e.event_type == EventType.QA_REVIEW_COMPLETE]
        rev_events = [e for e in events if e.event_type == EventType.REVISION_REQUESTED]
        assert len(qa_events) == 2, f"expected 2 QA_REVIEW_COMPLETE, got {len(qa_events)}"
        assert qa_events[0].data["verdict"] == "revise_code"
        assert qa_events[1].data["verdict"] == "approve"
        assert len(rev_events) == 1
        assert rev_events[0].data["verdict"] == "revise_code"

    async def test_ddc_code_revision_context_includes_customer_config_v2(self, ddc_ecommerce):
        """On code revision, Developer must still receive customer_config_v2."""
        events: list[PipelineEvent] = []
        ra_result = RAOutputDDC(
            needs_clarification=False,
            reasoning="Ready.",
            finalized_config=ddc_ecommerce,
        )
        dev_contexts: list[dict] = []

        async def _dev_execute(ctx, *args, **kwargs):
            dev_contexts.append(dict(ctx))
            return _make_code_output()

        dev = MagicMock(spec=BaseAgent)
        dev.execute = AsyncMock(side_effect=_dev_execute)

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
            "requirements_analyst": _make_mock_agent(AgentName.REQUIREMENTS_ANALYST, ra_result),
            "solution_architect": _make_mock_agent(AgentName.SOLUTION_ARCHITECT, _make_technical_design()),
            "developer": dev,
            "qa_reviewer": qa,
        }
        runner = self._make_runner(agents, events)
        await runner.run(ddc_ecommerce)

        assert len(dev_contexts) == 2
        revision_ctx = dev_contexts[1]
        assert "customer_config_v2" in revision_ctx
        assert "previous_code" in revision_ctx
        assert "finalized_config" not in revision_ctx
