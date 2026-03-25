"""
Integration test — full pipeline from CustomerConfig to final output.

Runs the complete Aegis pipeline with mocked LLM responses, verifying
that all 4 agents execute in sequence, context flows correctly, events
are emitted, and the pipeline reaches COMPLETE with a valid outcome.

This does NOT call a real LLM. Each agent's LLM response is pre-canned
JSON matching the expected output schema.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents import Developer, QAReviewer, RequirementsAnalyst, SolutionArchitect
from app.pipeline.runner import PipelineRunner
from app.schemas.pipeline_events import EventType, PipelineState


# ===========================================================================
# Pre-canned LLM responses (valid JSON matching each agent's output schema)
# ===========================================================================

RA_RESPONSE = {
    "needs_clarification": False,
    "reasoning": "The customer's requirements are clear enough to proceed.",
    "finalized_config": {
        "config": {
            "business_context": {
                "name": "Cafe Latte",
                "industry": "food_and_beverage",
                "description": "A small coffee shop chain with 3 locations.",
                "size": "6-20",
            },
            "problem_statement": {
                "problem": "We need an online ordering system for pickup orders.",
                "users": ["customers", "employees"],
                "current_process": "Phone calls and walk-ins only.",
            },
            "features": {
                "requested": [
                    {"description": "Menu display with categories", "priority": 1},
                    {"description": "Shopping cart and checkout", "priority": 2},
                ]
            },
            "data": {"entities": "Menu items, orders, customers"},
        },
        "assumptions": [
            {
                "field_path": "technical.auth_required",
                "original_value": None,
                "assumed_value": "false",
                "reasoning": "Simple ordering system does not require auth.",
            }
        ],
        "clarification_history": [],
        "project_summary": "An online ordering system for Cafe Latte.",
        "is_complete": True,
    },
}

SA_RESPONSE = {
    "reasoning": "Standard CRUD app with menu and order management.",
    "project_name": "cafe-ordering",
    "tech_summary": "Next.js 14 with App Router, Tailwind CSS, better-sqlite3",
    "data_models": [
        {
            "name": "MenuItem",
            "description": "A menu item available for ordering",
            "fields": [
                {"name": "id", "type": "integer", "required": True},
                {"name": "name", "type": "string", "required": True},
                {"name": "price", "type": "float", "required": True},
                {"name": "category", "type": "string", "required": True},
            ],
            "relationships": ["has_many:OrderItem"],
        },
        {
            "name": "Order",
            "description": "A customer pickup order",
            "fields": [
                {"name": "id", "type": "integer", "required": True},
                {"name": "status", "type": "enum", "required": True},
                {"name": "created_at", "type": "datetime", "required": True},
            ],
            "relationships": ["has_many:OrderItem"],
        },
    ],
    "api_endpoints": [
        {
            "method": "GET",
            "path": "/api/menu",
            "description": "List all menu items",
            "response": "Array of MenuItem objects",
        },
        {
            "method": "POST",
            "path": "/api/orders",
            "description": "Create a new order",
            "request_body": "Order details with items",
            "response": "Created Order object",
        },
    ],
    "ui_components": [
        {
            "name": "MenuPage",
            "type": "page",
            "description": "Displays menu items grouped by category",
            "features": ["Menu display with categories"],
            "data_sources": ["/api/menu"],
        },
        {
            "name": "CartPage",
            "type": "page",
            "description": "Shopping cart and checkout flow",
            "features": ["Shopping cart and checkout"],
            "data_sources": ["/api/orders"],
        },
    ],
    "file_structure": [
        {"path": "app/menu/page.js", "purpose": "Menu display page"},
        {"path": "app/cart/page.js", "purpose": "Cart and checkout page"},
        {"path": "app/api/menu/route.js", "purpose": "Menu API route handler"},
        {"path": "app/api/orders/route.js", "purpose": "Order API route handler"},
    ],
    "dependencies": ["next", "tailwindcss", "better-sqlite3"],
}

DEV_RESPONSE = {
    "reasoning": "Implemented all features following the technical design.",
    "project_name": "cafe-ordering",
    "files": [
        {
            "path": "app/menu/page.js",
            "content": "export default function Menu() { return <div className='p-4'>Menu</div>; }",
            "language": "javascript",
            "description": "Menu display page",
        },
        {
            "path": "app/cart/page.js",
            "content": "'use client';\nexport default function Cart() { return <div className='p-4'>Cart</div>; }",
            "language": "javascript",
            "description": "Cart and checkout page",
        },
        {
            "path": "app/api/menu/route.js",
            "content": "import { NextResponse } from 'next/server';\nexport async function GET() { return NextResponse.json([]); }",
            "language": "javascript",
            "description": "Menu API route handler",
        },
        {
            "path": "app/api/orders/route.js",
            "content": "import { NextResponse } from 'next/server';\nexport async function POST(request) { return NextResponse.json({id: 1}); }",
            "language": "javascript",
            "description": "Order API route handler",
        },
    ],
    "setup_instructions": "npm install && npm run dev",
    "features_implemented": [
        "Menu display with categories",
        "Shopping cart and checkout",
    ],
    "known_limitations": [],
}

QA_RESPONSE = {
    "reasoning": "All requirements are covered. Code is clean and consistent.",
    "verdict": "approve",
    "issues": [],
    "requirements_coverage": {
        "Menu display with categories": True,
        "Shopping cart and checkout": True,
    },
    "code_quality_score": 4,
    "summary": "Your ordering application is ready. It includes a full menu display and checkout system.",
}


def _mock_llm_response(payload: dict) -> MagicMock:
    """Build a mock Anthropic API response from a dict."""
    content_block = MagicMock()
    content_block.text = json.dumps(payload)
    usage = MagicMock()
    usage.input_tokens = 500
    usage.output_tokens = 300
    response = MagicMock()
    response.content = [content_block]
    response.usage = usage
    return response


def _build_pipeline_with_mocked_llm() -> tuple[PipelineRunner, list]:
    """
    Build a full pipeline with real agent instances but mocked LLM clients.
    Returns (runner, events_list).
    """
    ra = RequirementsAnalyst()
    sa = SolutionArchitect()
    dev = Developer()
    qa = QAReviewer()

    # Wire each agent to return its pre-canned response
    ra.client = MagicMock()
    ra.client.messages.create = AsyncMock(return_value=_mock_llm_response(RA_RESPONSE))

    sa.client = MagicMock()
    sa.client.messages.create = AsyncMock(return_value=_mock_llm_response(SA_RESPONSE))

    dev.client = MagicMock()
    dev.client.messages.create = AsyncMock(return_value=_mock_llm_response(DEV_RESPONSE))

    qa.client = MagicMock()
    qa.client.messages.create = AsyncMock(return_value=_mock_llm_response(QA_RESPONSE))

    agents = {
        "requirements_analyst": ra,
        "solution_architect": sa,
        "developer": dev,
        "qa_reviewer": qa,
    }

    events = []
    runner = PipelineRunner(agents=agents, emit_event=events.append)
    return runner, events


# ===========================================================================
# Integration tests
# ===========================================================================


class TestFullPipelineIntegration:
    """End-to-end pipeline run: CustomerConfig → COMPLETE."""

    @pytest.mark.asyncio
    async def test_pipeline_reaches_complete(self, valid_customer_config):
        runner, _ = _build_pipeline_with_mocked_llm()
        result = await runner.run(valid_customer_config)
        assert result.state == PipelineState.COMPLETE

    @pytest.mark.asyncio
    async def test_pipeline_outcome_is_success(self, valid_customer_config):
        runner, _ = _build_pipeline_with_mocked_llm()
        result = await runner.run(valid_customer_config)
        assert result.outcome == "success"

    @pytest.mark.asyncio
    async def test_pipeline_completed_at_is_set(self, valid_customer_config):
        runner, _ = _build_pipeline_with_mocked_llm()
        result = await runner.run(valid_customer_config)
        assert result.completed_at is not None

    @pytest.mark.asyncio
    async def test_all_four_agents_called(self, valid_customer_config):
        runner, _ = _build_pipeline_with_mocked_llm()
        await runner.run(valid_customer_config)

        ra = runner.agents["requirements_analyst"]
        sa = runner.agents["solution_architect"]
        dev = runner.agents["developer"]
        qa = runner.agents["qa_reviewer"]

        assert ra.client.messages.create.call_count == 1
        assert sa.client.messages.create.call_count == 1
        assert dev.client.messages.create.call_count == 1
        assert qa.client.messages.create.call_count == 1

    @pytest.mark.asyncio
    async def test_pipeline_started_event_emitted(self, valid_customer_config):
        runner, events = _build_pipeline_with_mocked_llm()
        await runner.run(valid_customer_config)
        types = [e.event_type for e in events]
        assert EventType.PIPELINE_STARTED in types

    @pytest.mark.asyncio
    async def test_pipeline_complete_event_emitted(self, valid_customer_config):
        runner, events = _build_pipeline_with_mocked_llm()
        await runner.run(valid_customer_config)
        types = [e.event_type for e in events]
        assert EventType.PIPELINE_COMPLETE in types

    @pytest.mark.asyncio
    async def test_config_finalized_event_emitted(self, valid_customer_config):
        runner, events = _build_pipeline_with_mocked_llm()
        await runner.run(valid_customer_config)
        types = [e.event_type for e in events]
        assert EventType.CONFIG_FINALIZED in types

    @pytest.mark.asyncio
    async def test_agent_start_events_for_all_agents(self, valid_customer_config):
        runner, events = _build_pipeline_with_mocked_llm()
        await runner.run(valid_customer_config)

        start_events = [e for e in events if e.event_type == EventType.AGENT_START]
        agents_started = {e.agent for e in start_events}
        assert agents_started == {
            "requirements_analyst",
            "solution_architect",
            "developer",
            "qa_reviewer",
        }

    @pytest.mark.asyncio
    async def test_agent_complete_events_for_all_agents(self, valid_customer_config):
        runner, events = _build_pipeline_with_mocked_llm()
        await runner.run(valid_customer_config)

        complete_events = [e for e in events if e.event_type == EventType.AGENT_COMPLETE]
        agents_completed = {e.agent for e in complete_events}
        assert agents_completed == {
            "requirements_analyst",
            "solution_architect",
            "developer",
            "qa_reviewer",
        }

    @pytest.mark.asyncio
    async def test_context_has_finalized_config_after_ra(self, valid_customer_config):
        runner, _ = _build_pipeline_with_mocked_llm()
        await runner.run(valid_customer_config)
        assert "finalized_config" in runner.context

    @pytest.mark.asyncio
    async def test_context_has_technical_design_after_sa(self, valid_customer_config):
        runner, _ = _build_pipeline_with_mocked_llm()
        await runner.run(valid_customer_config)
        assert "technical_design" in runner.context

    @pytest.mark.asyncio
    async def test_context_has_code_output_after_dev(self, valid_customer_config):
        runner, _ = _build_pipeline_with_mocked_llm()
        await runner.run(valid_customer_config)
        assert "code_output" in runner.context

    @pytest.mark.asyncio
    async def test_context_has_qa_review_after_qa(self, valid_customer_config):
        runner, _ = _build_pipeline_with_mocked_llm()
        await runner.run(valid_customer_config)
        assert "qa_review" in runner.context

    @pytest.mark.asyncio
    async def test_tokens_accumulated(self, valid_customer_config):
        runner, _ = _build_pipeline_with_mocked_llm()
        result = await runner.run(valid_customer_config)
        # Each agent emits tokens on both LLM_CALL_COMPLETE and AGENT_COMPLETE
        # 4 agents x 500 input tokens x 2 events = 4000
        assert result.total_tokens.input_tokens == 4000
        # 4 agents x 300 output tokens x 2 events = 2400
        assert result.total_tokens.output_tokens == 2400

    @pytest.mark.asyncio
    async def test_no_feedback_cycles(self, valid_customer_config):
        runner, _ = _build_pipeline_with_mocked_llm()
        result = await runner.run(valid_customer_config)
        assert result.feedback_cycles.get("code_revisions", 0) == 0
        assert result.feedback_cycles.get("design_revisions", 0) == 0

    @pytest.mark.asyncio
    async def test_run_id_consistent_across_events(self, valid_customer_config):
        runner, events = _build_pipeline_with_mocked_llm()
        result = await runner.run(valid_customer_config)
        for event in events:
            assert event.run_id == result.run_id

    @pytest.mark.asyncio
    async def test_events_stored_on_pipeline_run(self, valid_customer_config):
        runner, events = _build_pipeline_with_mocked_llm()
        result = await runner.run(valid_customer_config)
        assert len(result.events) == len(events)

    @pytest.mark.asyncio
    async def test_final_code_output_has_correct_project_name(self, valid_customer_config):
        runner, _ = _build_pipeline_with_mocked_llm()
        await runner.run(valid_customer_config)
        code_output = runner.context["code_output"]
        assert code_output.project_name == "cafe-ordering"

    @pytest.mark.asyncio
    async def test_final_code_output_has_all_files(self, valid_customer_config):
        runner, _ = _build_pipeline_with_mocked_llm()
        await runner.run(valid_customer_config)
        code_output = runner.context["code_output"]
        assert len(code_output.files) == 4

    @pytest.mark.asyncio
    async def test_qa_verdict_is_approve(self, valid_customer_config):
        runner, _ = _build_pipeline_with_mocked_llm()
        await runner.run(valid_customer_config)
        qa_review = runner.context["qa_review"]
        assert qa_review.verdict.value == "approve"


class TestPipelineWithClarification:
    """Integration test with a clarification round."""

    @pytest.mark.asyncio
    async def test_clarification_then_resume_completes(self, valid_customer_config):
        """Pipeline pauses for clarification, then completes after resume."""
        ra = RequirementsAnalyst()
        sa = SolutionArchitect()
        dev = Developer()
        qa = QAReviewer()

        # First RA call: needs clarification
        clarification_response = {
            "needs_clarification": True,
            "reasoning": "Need to clarify payment method.",
            "questions": [
                {
                    "id": "q1",
                    "topic": "payments",
                    "original_input": "Shopping cart and checkout",
                    "question": "How should customers pay?",
                    "suggestions": ["Credit card", "Cash on pickup", "Both"],
                }
            ],
        }

        # Second RA call: finalize
        finalize_response = RA_RESPONSE

        ra.client = MagicMock()
        ra.client.messages.create = AsyncMock(
            side_effect=[
                _mock_llm_response(clarification_response),
                _mock_llm_response(finalize_response),
            ]
        )

        sa.client = MagicMock()
        sa.client.messages.create = AsyncMock(return_value=_mock_llm_response(SA_RESPONSE))

        dev.client = MagicMock()
        dev.client.messages.create = AsyncMock(return_value=_mock_llm_response(DEV_RESPONSE))

        qa.client = MagicMock()
        qa.client.messages.create = AsyncMock(return_value=_mock_llm_response(QA_RESPONSE))

        agents = {
            "requirements_analyst": ra,
            "solution_architect": sa,
            "developer": dev,
            "qa_reviewer": qa,
        }

        events = []
        runner = PipelineRunner(agents=agents, emit_event=events.append)

        # First run — should pause at CLARIFICATION
        result = await runner.run(valid_customer_config)
        assert result.state == PipelineState.CLARIFICATION

        # Resume with answers
        result = await runner.resume(answers={"q1": "Cash on pickup"})
        assert result.state == PipelineState.COMPLETE
        assert result.outcome == "success"


class TestPipelineWithCodeRevision:
    """Integration test with a code revision loop."""

    @pytest.mark.asyncio
    async def test_code_revision_then_approve(self, valid_customer_config):
        """QA says revise_code, Developer re-runs, QA approves."""
        ra = RequirementsAnalyst()
        sa = SolutionArchitect()
        dev = Developer()
        qa = QAReviewer()

        ra.client = MagicMock()
        ra.client.messages.create = AsyncMock(return_value=_mock_llm_response(RA_RESPONSE))

        sa.client = MagicMock()
        sa.client.messages.create = AsyncMock(return_value=_mock_llm_response(SA_RESPONSE))

        dev.client = MagicMock()
        dev.client.messages.create = AsyncMock(return_value=_mock_llm_response(DEV_RESPONSE))

        # QA: first call revise_code, second call approve
        revise_response = {
            "reasoning": "Missing error handling in order creation.",
            "verdict": "revise_code",
            "issues": [
                {
                    "id": "issue-1",
                    "severity": "major",
                    "category": "code_quality",
                    "affected_file": "server/routes/orders.js",
                    "description": "No error handling for invalid order data.",
                    "suggestion": "Add try-catch and validate request body.",
                }
            ],
            "requirements_coverage": {
                "Menu display with categories": True,
                "Shopping cart and checkout": True,
            },
            "code_quality_score": 2,
            "summary": "The app works but needs better error handling.",
        }

        qa.client = MagicMock()
        qa.client.messages.create = AsyncMock(
            side_effect=[
                _mock_llm_response(revise_response),
                _mock_llm_response(QA_RESPONSE),
            ]
        )

        agents = {
            "requirements_analyst": ra,
            "solution_architect": sa,
            "developer": dev,
            "qa_reviewer": qa,
        }

        events = []
        runner = PipelineRunner(agents=agents, emit_event=events.append)
        result = await runner.run(valid_customer_config)

        assert result.state == PipelineState.COMPLETE
        assert result.outcome == "success"
        assert result.feedback_cycles.get("code_revisions") == 1

        # Developer should have been called twice (initial + revision)
        assert dev.client.messages.create.call_count == 2
        # QA should have been called twice
        assert qa.client.messages.create.call_count == 2

        # Check revision event was emitted
        types = [e.event_type for e in events]
        assert EventType.REVISION_STARTED in types
