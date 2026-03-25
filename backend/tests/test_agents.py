"""
Tests for the Solution Architect, Developer, and QA Reviewer agents.

Coverage per agent:
  1. __init__() — name, system_prompt, output_schema wired correctly
  2. build_user_prompt() — normal mode contains expected content
  3. build_user_prompt() — revision mode (SA: previous_design+qa_review;
     Dev: previous_code+qa_review; QA: no revision mode)
  4. build_user_prompt() — correct context keys are consumed
  5. execute() with mocked LLM returning valid JSON — output matches schema
  6. Event emission — AGENT_START and AGENT_COMPLETE emitted with correct fields
  7. Validation retry — first response invalid schema, second valid → succeeds
  8. Double failure — both attempts invalid → raises ValueError + ERROR event
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.developer import Developer
from app.agents.qa_reviewer import QAReviewer
from app.agents.solution_architect import SolutionArchitect
from app.schemas.agent_outputs import (
    CodeOutput,
    QAReview,
    ReviewVerdict,
    TechnicalDesign,
)
from app.schemas.customer_config import FinalizedConfig
from app.schemas.pipeline_events import AgentName, EventType, PipelineEvent


# ===========================================================================
# Shared payload builders
# ===========================================================================

def _technical_design_payload() -> dict:
    """Minimal valid TechnicalDesign dict (mirrors the Pydantic schema)."""
    return {
        "reasoning": "Designing a Next.js 14 application with Tailwind CSS for the ordering system.",
        "project_name": "cafe-latte-ordering",
        "tech_summary": "Next.js 14 with App Router, Tailwind CSS, better-sqlite3",
        "data_models": [
            {
                "name": "MenuItem",
                "description": "A single item on the cafe menu.",
                "fields": [
                    {
                        "name": "id",
                        "type": "integer",
                        "required": True,
                        "description": "Primary key",
                        "constraints": None,
                    },
                    {
                        "name": "name",
                        "type": "string",
                        "required": True,
                        "description": "Item name",
                        "constraints": "max_length:255",
                    },
                    {
                        "name": "price",
                        "type": "float",
                        "required": True,
                        "description": "Item price",
                        "constraints": None,
                    },
                ],
                "relationships": [],
            }
        ],
        "api_endpoints": [
            {
                "method": "GET",
                "path": "/api/menu",
                "description": "Retrieve the full menu.",
                "request_body": None,
                "response": "List of MenuItem objects.",
            }
        ],
        "ui_components": [
            {
                "name": "MenuPage",
                "type": "page",
                "description": "Displays the full menu to customers.",
                "features": ["Browse menu", "Filter by category"],
                "data_sources": ["/api/menu"],
            }
        ],
        "file_structure": [
            {"path": "app/api/menu/route.js", "purpose": "Menu API route handler."},
            {"path": "app/menu/page.js", "purpose": "Menu page component."},
        ],
        "dependencies": ["next", "tailwindcss", "better-sqlite3"],
        "notes": None,
    }


def _code_output_payload() -> dict:
    """Minimal valid CodeOutput dict."""
    return {
        "reasoning": "Implemented all endpoints and components per the design.",
        "project_name": "cafe-latte-ordering",
        "files": [
            {
                "path": "app/api/menu/route.js",
                "content": "import { NextResponse } from 'next/server';\nexport async function GET() { return NextResponse.json([]); }\n",
                "language": "javascript",
                "description": "Menu API route handler.",
            },
            {
                "path": "app/menu/page.js",
                "content": "export default function MenuPage() { return <div className='p-4'>Menu</div>; }",
                "language": "javascript",
                "description": "Menu page component.",
            },
        ],
        "setup_instructions": "npm install && npm run dev",
        "features_implemented": [
            "Menu display with categories",
            "Shopping cart and checkout",
        ],
        "known_limitations": [],
    }


def _qa_review_payload(verdict: str = "approve") -> dict:
    """Minimal valid QAReview dict."""
    return {
        "reasoning": "The implementation covers all stated requirements with good quality.",
        "verdict": verdict,
        "issues": [],
        "requirements_coverage": {
            "Menu display with categories": True,
            "Shopping cart and checkout": True,
        },
        "code_quality_score": 4,
        "summary": "Your application has been built and reviewed. Everything looks good.",
    }


def _qa_review_with_issues_payload(verdict: str = "revise_code") -> dict:
    """QAReview dict with one issue and a non-approve verdict."""
    return {
        "reasoning": "Missing error handling in the API layer.",
        "verdict": verdict,
        "issues": [
            {
                "id": "issue-1",
                "severity": "major",
                "category": "functional",
                "affected_file": "backend/main.py",
                "description": "The /api/menu endpoint does not handle database errors.",
                "suggestion": "Wrap the database call in a try-except and return HTTP 500 on failure.",
            }
        ],
        "requirements_coverage": {
            "Menu display with categories": True,
            "Shopping cart and checkout": False,
        },
        "code_quality_score": 2,
        "summary": "The application needs some fixes before it is ready for delivery.",
    }


def _make_response(payload: dict) -> MagicMock:
    """Build a mock Anthropic messages.create() response."""
    content_block = MagicMock()
    content_block.text = json.dumps(payload)
    usage = MagicMock()
    usage.input_tokens = 150
    usage.output_tokens = 300
    response = MagicMock()
    response.content = [content_block]
    response.usage = usage
    return response


def _make_raw_text_response(text: str) -> MagicMock:
    """Build a mock response that returns raw text (not valid JSON)."""
    content_block = MagicMock()
    content_block.text = text
    usage = MagicMock()
    usage.input_tokens = 100
    usage.output_tokens = 200
    response = MagicMock()
    response.content = [content_block]
    response.usage = usage
    return response


def _event_types(events: list[PipelineEvent]) -> list[EventType]:
    return [e.event_type for e in events]


# ===========================================================================
# 1. Solution Architect
# ===========================================================================

class TestSolutionArchitectInit:
    """__init__() wires the correct name, schema, and non-empty system prompt."""

    def test_agent_name_is_solution_architect(self, mock_anthropic):
        agent = SolutionArchitect()
        assert agent.name == AgentName.SOLUTION_ARCHITECT

    def test_output_schema_is_technical_design(self, mock_anthropic):
        agent = SolutionArchitect()
        assert agent.output_schema is TechnicalDesign

    def test_system_prompt_is_non_empty(self, mock_anthropic):
        agent = SolutionArchitect()
        assert len(agent.system_prompt) > 100

    def test_system_prompt_mentions_solution_architect(self, mock_anthropic):
        agent = SolutionArchitect()
        assert "Solution Architect" in agent.system_prompt


class TestSolutionArchitectBuildUserPrompt:
    """build_user_prompt() — normal and revision modes."""

    @pytest.fixture(autouse=True)
    def _agent(self, mock_anthropic):
        self.agent = SolutionArchitect()

    def test_normal_mode_contains_design_application_header(
        self, valid_finalized_config: FinalizedConfig
    ):
        prompt = self.agent.build_user_prompt({"finalized_config": valid_finalized_config})
        assert "DESIGN THE APPLICATION" in prompt

    def test_normal_mode_contains_finalized_requirements_section(
        self, valid_finalized_config: FinalizedConfig
    ):
        prompt = self.agent.build_user_prompt({"finalized_config": valid_finalized_config})
        assert "FINALIZED REQUIREMENTS" in prompt

    def test_normal_mode_contains_business_name_from_config(
        self, valid_finalized_config: FinalizedConfig
    ):
        prompt = self.agent.build_user_prompt({"finalized_config": valid_finalized_config})
        assert "Cafe Latte" in prompt

    def test_normal_mode_does_not_include_revision_header(
        self, valid_finalized_config: FinalizedConfig
    ):
        prompt = self.agent.build_user_prompt({"finalized_config": valid_finalized_config})
        assert "DESIGN REVISION REQUESTED" not in prompt

    def test_revision_mode_contains_revision_header(
        self, valid_finalized_config: FinalizedConfig
    ):
        previous_design = TechnicalDesign.model_validate(_technical_design_payload())
        qa_review = QAReview.model_validate(_qa_review_with_issues_payload("revise_design"))
        context = {
            "finalized_config": valid_finalized_config,
            "previous_design": previous_design,
            "qa_review": qa_review,
        }
        prompt = self.agent.build_user_prompt(context)
        assert "DESIGN REVISION REQUESTED" in prompt

    def test_revision_mode_contains_qa_review_feedback_section(
        self, valid_finalized_config: FinalizedConfig
    ):
        previous_design = TechnicalDesign.model_validate(_technical_design_payload())
        qa_review = QAReview.model_validate(_qa_review_with_issues_payload("revise_design"))
        context = {
            "finalized_config": valid_finalized_config,
            "previous_design": previous_design,
            "qa_review": qa_review,
        }
        prompt = self.agent.build_user_prompt(context)
        assert "QA REVIEW FEEDBACK" in prompt

    def test_revision_mode_contains_previous_design_section(
        self, valid_finalized_config: FinalizedConfig
    ):
        previous_design = TechnicalDesign.model_validate(_technical_design_payload())
        qa_review = QAReview.model_validate(_qa_review_with_issues_payload("revise_design"))
        context = {
            "finalized_config": valid_finalized_config,
            "previous_design": previous_design,
            "qa_review": qa_review,
        }
        prompt = self.agent.build_user_prompt(context)
        assert "YOUR PREVIOUS DESIGN" in prompt

    def test_revision_mode_contains_project_name_from_previous_design(
        self, valid_finalized_config: FinalizedConfig
    ):
        previous_design = TechnicalDesign.model_validate(_technical_design_payload())
        qa_review = QAReview.model_validate(_qa_review_with_issues_payload("revise_design"))
        context = {
            "finalized_config": valid_finalized_config,
            "previous_design": previous_design,
            "qa_review": qa_review,
        }
        prompt = self.agent.build_user_prompt(context)
        assert "cafe-latte-ordering" in prompt

    def test_revision_mode_requires_both_previous_design_and_qa_review(
        self, valid_finalized_config: FinalizedConfig
    ):
        """With only previous_design (no qa_review), mode should fall through to normal."""
        previous_design = TechnicalDesign.model_validate(_technical_design_payload())
        context = {
            "finalized_config": valid_finalized_config,
            "previous_design": previous_design,
        }
        prompt = self.agent.build_user_prompt(context)
        assert "DESIGN THE APPLICATION" in prompt
        assert "DESIGN REVISION REQUESTED" not in prompt


class TestSolutionArchitectExecute:
    """execute() with mocked LLM — happy path, retry, double failure."""

    @pytest.fixture(autouse=True)
    def _agent(self, mock_anthropic):
        self.agent = SolutionArchitect()
        self.mock_client = mock_anthropic

    @pytest.mark.asyncio
    async def test_execute_returns_technical_design_on_valid_response(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(_technical_design_payload())
        )

        result = await self.agent.execute(
            context={"finalized_config": valid_finalized_config},
            run_id=sample_run_id,
            emit_event=emit,
        )

        assert isinstance(result, TechnicalDesign)
        assert result.project_name == "cafe-latte-ordering"

    @pytest.mark.asyncio
    async def test_execute_result_has_correct_data_models(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(_technical_design_payload())
        )

        result = await self.agent.execute(
            context={"finalized_config": valid_finalized_config},
            run_id=sample_run_id,
            emit_event=emit,
        )

        assert len(result.data_models) == 1
        assert result.data_models[0].name == "MenuItem"

    @pytest.mark.asyncio
    async def test_execute_result_has_correct_api_endpoints(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(_technical_design_payload())
        )

        result = await self.agent.execute(
            context={"finalized_config": valid_finalized_config},
            run_id=sample_run_id,
            emit_event=emit,
        )

        assert result.api_endpoints[0].method == "GET"
        assert result.api_endpoints[0].path == "/api/menu"

    @pytest.mark.asyncio
    async def test_execute_handles_markdown_json_fences(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        raw_json = json.dumps(_technical_design_payload())
        content_block = MagicMock()
        content_block.text = f"```json\n{raw_json}\n```"
        usage = MagicMock()
        usage.input_tokens = 100
        usage.output_tokens = 200
        fenced_response = MagicMock()
        fenced_response.content = [content_block]
        fenced_response.usage = usage
        self.mock_client.messages.create = AsyncMock(return_value=fenced_response)

        result = await self.agent.execute(
            context={"finalized_config": valid_finalized_config},
            run_id=sample_run_id,
            emit_event=emit,
        )

        assert isinstance(result, TechnicalDesign)

    @pytest.mark.asyncio
    async def test_execute_retries_on_schema_validation_failure(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        # Missing required data_models → ValidationError on first call
        invalid_payload = {
            "reasoning": "ok",
            "project_name": "cafe-latte-ordering",
            "tech_summary": "Next.js 14",
            "data_models": [],  # min_length=1 violation
            "api_endpoints": [{"method": "GET", "path": "/api/menu", "description": "ok", "request_body": None, "response": "ok"}],
            "ui_components": [{"name": "MenuPage", "type": "page", "description": "ok", "features": [], "data_sources": []}],
            "file_structure": [{"path": "app/page.js", "purpose": "entry"}],
        }
        self.mock_client.messages.create = AsyncMock(
            side_effect=[
                _make_response(invalid_payload),
                _make_response(_technical_design_payload()),
            ]
        )

        result = await self.agent.execute(
            context={"finalized_config": valid_finalized_config},
            run_id=sample_run_id,
            emit_event=emit,
        )

        assert isinstance(result, TechnicalDesign)
        assert self.mock_client.messages.create.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_raises_value_error_after_double_schema_failure(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        invalid_payload = {
            "reasoning": "ok",
            "project_name": "cafe-latte-ordering",
            "tech_summary": "Next.js 14",
            "data_models": [],  # always fails
            "api_endpoints": [{"method": "GET", "path": "/api/menu", "description": "ok", "request_body": None, "response": "ok"}],
            "ui_components": [{"name": "MenuPage", "type": "page", "description": "ok", "features": [], "data_sources": []}],
            "file_structure": [{"path": "app/page.js", "purpose": "entry"}],
        }
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(invalid_payload)
        )

        with pytest.raises(ValueError, match="failed output validation after retry"):
            await self.agent.execute(
                context={"finalized_config": valid_finalized_config},
                run_id=sample_run_id,
                emit_event=emit,
            )

        assert self.mock_client.messages.create.call_count == 2


class TestSolutionArchitectEventEmission:
    """Verifies AGENT_START and AGENT_COMPLETE events for SA."""

    @pytest.fixture(autouse=True)
    def _agent(self, mock_anthropic):
        self.agent = SolutionArchitect()
        self.mock_client = mock_anthropic

    @pytest.mark.asyncio
    async def test_emits_agent_start_event(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(_technical_design_payload())
        )

        await self.agent.execute(
            context={"finalized_config": valid_finalized_config},
            run_id=sample_run_id,
            emit_event=emit,
        )

        types = _event_types(events)
        assert EventType.AGENT_START in types

    @pytest.mark.asyncio
    async def test_emits_agent_complete_event(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(_technical_design_payload())
        )

        await self.agent.execute(
            context={"finalized_config": valid_finalized_config},
            run_id=sample_run_id,
            emit_event=emit,
        )

        types = _event_types(events)
        assert EventType.AGENT_COMPLETE in types

    @pytest.mark.asyncio
    async def test_agent_start_is_emitted_before_agent_complete(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(_technical_design_payload())
        )

        await self.agent.execute(
            context={"finalized_config": valid_finalized_config},
            run_id=sample_run_id,
            emit_event=emit,
        )

        types = _event_types(events)
        assert types.index(EventType.AGENT_START) < types.index(EventType.AGENT_COMPLETE)

    @pytest.mark.asyncio
    async def test_agent_start_event_has_correct_agent_name(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(_technical_design_payload())
        )

        await self.agent.execute(
            context={"finalized_config": valid_finalized_config},
            run_id=sample_run_id,
            emit_event=emit,
        )

        start_event = next(e for e in events if e.event_type == EventType.AGENT_START)
        assert start_event.agent == AgentName.SOLUTION_ARCHITECT

    @pytest.mark.asyncio
    async def test_agent_start_event_has_correct_run_id(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(_technical_design_payload())
        )

        await self.agent.execute(
            context={"finalized_config": valid_finalized_config},
            run_id=sample_run_id,
            emit_event=emit,
        )

        start_event = next(e for e in events if e.event_type == EventType.AGENT_START)
        assert start_event.run_id == sample_run_id

    @pytest.mark.asyncio
    async def test_agent_complete_event_carries_token_usage(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        response = _make_response(_technical_design_payload())
        response.usage.input_tokens = 400
        response.usage.output_tokens = 120
        self.mock_client.messages.create = AsyncMock(return_value=response)

        await self.agent.execute(
            context={"finalized_config": valid_finalized_config},
            run_id=sample_run_id,
            emit_event=emit,
        )

        complete_event = next(e for e in events if e.event_type == EventType.AGENT_COMPLETE)
        assert complete_event.tokens_used is not None
        assert complete_event.tokens_used.input_tokens == 400
        assert complete_event.tokens_used.output_tokens == 120

    @pytest.mark.asyncio
    async def test_double_failure_emits_error_event_not_agent_complete(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        invalid_payload = {
            "reasoning": "ok",
            "project_name": "x",
            "tech_summary": "y",
            "data_models": [],
            "api_endpoints": [{"method": "GET", "path": "/", "description": "d", "request_body": None, "response": "r"}],
            "ui_components": [{"name": "P", "type": "page", "description": "d", "features": [], "data_sources": []}],
            "file_structure": [{"path": "f.py", "purpose": "p"}],
        }
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(invalid_payload)
        )

        with pytest.raises(ValueError):
            await self.agent.execute(
                context={"finalized_config": valid_finalized_config},
                run_id=sample_run_id,
                emit_event=emit,
            )

        types = _event_types(events)
        assert EventType.ERROR in types
        assert EventType.AGENT_COMPLETE not in types

    @pytest.mark.asyncio
    async def test_json_decode_error_triggers_retry(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        """When the LLM returns invalid JSON, the agent retries once."""
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            side_effect=[
                _make_raw_text_response("This is not JSON at all"),
                _make_response(_technical_design_payload()),
            ]
        )

        result = await self.agent.execute(
            context={"finalized_config": valid_finalized_config},
            run_id=sample_run_id,
            emit_event=emit,
        )

        assert isinstance(result, TechnicalDesign)
        assert self.mock_client.messages.create.call_count == 2
        assert EventType.VALIDATION_FAILED in _event_types(events)

    @pytest.mark.asyncio
    async def test_json_decode_error_double_failure_raises(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        """When both attempts return invalid JSON, ValueError is raised."""
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_raw_text_response("NOT JSON {{{")
        )

        with pytest.raises(ValueError, match="failed output validation"):
            await self.agent.execute(
                context={"finalized_config": valid_finalized_config},
                run_id=sample_run_id,
                emit_event=emit,
            )

        assert EventType.ERROR in _event_types(events)


# ===========================================================================
# 2. Developer
# ===========================================================================

class TestDeveloperInit:
    """__init__() wires the correct name, schema, and non-empty system prompt."""

    def test_agent_name_is_developer(self, mock_anthropic):
        agent = Developer()
        assert agent.name == AgentName.DEVELOPER

    def test_output_schema_is_code_output(self, mock_anthropic):
        agent = Developer()
        assert agent.output_schema is CodeOutput

    def test_system_prompt_is_non_empty(self, mock_anthropic):
        agent = Developer()
        assert len(agent.system_prompt) > 100

    def test_system_prompt_mentions_developer(self, mock_anthropic):
        agent = Developer()
        assert "Developer" in agent.system_prompt


class TestDeveloperBuildUserPrompt:
    """build_user_prompt() — normal and revision modes."""

    @pytest.fixture(autouse=True)
    def _agent(self, mock_anthropic):
        self.agent = Developer()
        self.design = TechnicalDesign.model_validate(_technical_design_payload())

    def test_normal_mode_contains_implement_header(
        self, valid_finalized_config: FinalizedConfig
    ):
        context = {
            "finalized_config": valid_finalized_config,
            "technical_design": self.design,
        }
        prompt = self.agent.build_user_prompt(context)
        assert "IMPLEMENT THE APPLICATION" in prompt

    def test_normal_mode_contains_customer_requirements_section(
        self, valid_finalized_config: FinalizedConfig
    ):
        context = {
            "finalized_config": valid_finalized_config,
            "technical_design": self.design,
        }
        prompt = self.agent.build_user_prompt(context)
        assert "CUSTOMER REQUIREMENTS" in prompt

    def test_normal_mode_contains_technical_design_section(
        self, valid_finalized_config: FinalizedConfig
    ):
        context = {
            "finalized_config": valid_finalized_config,
            "technical_design": self.design,
        }
        prompt = self.agent.build_user_prompt(context)
        assert "TECHNICAL DESIGN" in prompt

    def test_normal_mode_contains_business_name_from_config(
        self, valid_finalized_config: FinalizedConfig
    ):
        context = {
            "finalized_config": valid_finalized_config,
            "technical_design": self.design,
        }
        prompt = self.agent.build_user_prompt(context)
        assert "Cafe Latte" in prompt

    def test_normal_mode_contains_project_name_from_design(
        self, valid_finalized_config: FinalizedConfig
    ):
        context = {
            "finalized_config": valid_finalized_config,
            "technical_design": self.design,
        }
        prompt = self.agent.build_user_prompt(context)
        assert "cafe-latte-ordering" in prompt

    def test_normal_mode_does_not_contain_revision_header(
        self, valid_finalized_config: FinalizedConfig
    ):
        context = {
            "finalized_config": valid_finalized_config,
            "technical_design": self.design,
        }
        prompt = self.agent.build_user_prompt(context)
        assert "CODE REVISION REQUESTED" not in prompt

    def test_revision_mode_contains_revision_header(
        self, valid_finalized_config: FinalizedConfig
    ):
        previous_code = CodeOutput.model_validate(_code_output_payload())
        qa_review = QAReview.model_validate(_qa_review_with_issues_payload("revise_code"))
        context = {
            "finalized_config": valid_finalized_config,
            "technical_design": self.design,
            "previous_code": previous_code,
            "qa_review": qa_review,
        }
        prompt = self.agent.build_user_prompt(context)
        assert "CODE REVISION REQUESTED" in prompt

    def test_revision_mode_contains_qa_review_feedback_section(
        self, valid_finalized_config: FinalizedConfig
    ):
        previous_code = CodeOutput.model_validate(_code_output_payload())
        qa_review = QAReview.model_validate(_qa_review_with_issues_payload("revise_code"))
        context = {
            "finalized_config": valid_finalized_config,
            "technical_design": self.design,
            "previous_code": previous_code,
            "qa_review": qa_review,
        }
        prompt = self.agent.build_user_prompt(context)
        assert "QA REVIEW FEEDBACK" in prompt

    def test_revision_mode_contains_qa_issue_description(
        self, valid_finalized_config: FinalizedConfig
    ):
        previous_code = CodeOutput.model_validate(_code_output_payload())
        qa_review = QAReview.model_validate(_qa_review_with_issues_payload("revise_code"))
        context = {
            "finalized_config": valid_finalized_config,
            "technical_design": self.design,
            "previous_code": previous_code,
            "qa_review": qa_review,
        }
        prompt = self.agent.build_user_prompt(context)
        # The issue description from the QA review payload should be serialised into the prompt
        assert "database errors" in prompt

    def test_revision_mode_requires_both_previous_code_and_qa_review(
        self, valid_finalized_config: FinalizedConfig
    ):
        """With only qa_review (no previous_code), mode falls through to normal."""
        qa_review = QAReview.model_validate(_qa_review_with_issues_payload("revise_code"))
        context = {
            "finalized_config": valid_finalized_config,
            "technical_design": self.design,
            "qa_review": qa_review,
        }
        prompt = self.agent.build_user_prompt(context)
        assert "IMPLEMENT THE APPLICATION" in prompt
        assert "CODE REVISION REQUESTED" not in prompt

    def test_revision_mode_instructs_to_include_all_files(
        self, valid_finalized_config: FinalizedConfig
    ):
        previous_code = CodeOutput.model_validate(_code_output_payload())
        qa_review = QAReview.model_validate(_qa_review_with_issues_payload("revise_code"))
        context = {
            "finalized_config": valid_finalized_config,
            "technical_design": self.design,
            "previous_code": previous_code,
            "qa_review": qa_review,
        }
        prompt = self.agent.build_user_prompt(context)
        assert "ALL files" in prompt or "all files" in prompt.lower()


class TestDeveloperExecute:
    """execute() with mocked LLM — happy path, retry, double failure."""

    @pytest.fixture(autouse=True)
    def _agent(self, mock_anthropic):
        self.agent = Developer()
        self.mock_client = mock_anthropic
        self.design = TechnicalDesign.model_validate(_technical_design_payload())

    @pytest.mark.asyncio
    async def test_execute_returns_code_output_on_valid_response(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(_code_output_payload())
        )

        result = await self.agent.execute(
            context={
                "finalized_config": valid_finalized_config,
                "technical_design": self.design,
            },
            run_id=sample_run_id,
            emit_event=emit,
        )

        assert isinstance(result, CodeOutput)
        assert result.project_name == "cafe-latte-ordering"

    @pytest.mark.asyncio
    async def test_execute_result_has_correct_file_count(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(_code_output_payload())
        )

        result = await self.agent.execute(
            context={
                "finalized_config": valid_finalized_config,
                "technical_design": self.design,
            },
            run_id=sample_run_id,
            emit_event=emit,
        )

        assert len(result.files) == 2

    @pytest.mark.asyncio
    async def test_execute_result_has_features_implemented(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(_code_output_payload())
        )

        result = await self.agent.execute(
            context={
                "finalized_config": valid_finalized_config,
                "technical_design": self.design,
            },
            run_id=sample_run_id,
            emit_event=emit,
        )

        assert "Menu display with categories" in result.features_implemented

    @pytest.mark.asyncio
    async def test_execute_retries_on_schema_validation_failure(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        # Missing required 'files' list triggers ValidationError
        invalid_payload = {
            "reasoning": "ok",
            "project_name": "cafe-latte-ordering",
            "files": [],  # min_length=1 violation
            "setup_instructions": "npm install",
            "features_implemented": ["Feature A"],
        }
        self.mock_client.messages.create = AsyncMock(
            side_effect=[
                _make_response(invalid_payload),
                _make_response(_code_output_payload()),
            ]
        )

        result = await self.agent.execute(
            context={
                "finalized_config": valid_finalized_config,
                "technical_design": self.design,
            },
            run_id=sample_run_id,
            emit_event=emit,
        )

        assert isinstance(result, CodeOutput)
        assert self.mock_client.messages.create.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_raises_value_error_after_double_schema_failure(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        invalid_payload = {
            "reasoning": "ok",
            "project_name": "cafe-latte-ordering",
            "files": [],  # always fails
            "setup_instructions": "npm install",
            "features_implemented": ["Feature A"],
        }
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(invalid_payload)
        )

        with pytest.raises(ValueError, match="failed output validation after retry"):
            await self.agent.execute(
                context={
                    "finalized_config": valid_finalized_config,
                    "technical_design": self.design,
                },
                run_id=sample_run_id,
                emit_event=emit,
            )

        assert self.mock_client.messages.create.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_handles_markdown_json_fences(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        raw_json = json.dumps(_code_output_payload())
        content_block = MagicMock()
        content_block.text = f"```json\n{raw_json}\n```"
        usage = MagicMock()
        usage.input_tokens = 100
        usage.output_tokens = 200
        fenced_response = MagicMock()
        fenced_response.content = [content_block]
        fenced_response.usage = usage
        self.mock_client.messages.create = AsyncMock(return_value=fenced_response)

        result = await self.agent.execute(
            context={
                "finalized_config": valid_finalized_config,
                "technical_design": self.design,
            },
            run_id=sample_run_id,
            emit_event=emit,
        )

        assert isinstance(result, CodeOutput)


class TestDeveloperEventEmission:
    """Verifies AGENT_START and AGENT_COMPLETE events for Developer."""

    @pytest.fixture(autouse=True)
    def _agent(self, mock_anthropic):
        self.agent = Developer()
        self.mock_client = mock_anthropic
        self.design = TechnicalDesign.model_validate(_technical_design_payload())

    @pytest.mark.asyncio
    async def test_emits_agent_start_event(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(_code_output_payload())
        )

        await self.agent.execute(
            context={
                "finalized_config": valid_finalized_config,
                "technical_design": self.design,
            },
            run_id=sample_run_id,
            emit_event=emit,
        )

        types = _event_types(events)
        assert EventType.AGENT_START in types

    @pytest.mark.asyncio
    async def test_emits_agent_complete_event(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(_code_output_payload())
        )

        await self.agent.execute(
            context={
                "finalized_config": valid_finalized_config,
                "technical_design": self.design,
            },
            run_id=sample_run_id,
            emit_event=emit,
        )

        types = _event_types(events)
        assert EventType.AGENT_COMPLETE in types

    @pytest.mark.asyncio
    async def test_agent_start_is_emitted_before_agent_complete(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(_code_output_payload())
        )

        await self.agent.execute(
            context={
                "finalized_config": valid_finalized_config,
                "technical_design": self.design,
            },
            run_id=sample_run_id,
            emit_event=emit,
        )

        types = _event_types(events)
        assert types.index(EventType.AGENT_START) < types.index(EventType.AGENT_COMPLETE)

    @pytest.mark.asyncio
    async def test_agent_start_event_has_correct_agent_name(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(_code_output_payload())
        )

        await self.agent.execute(
            context={
                "finalized_config": valid_finalized_config,
                "technical_design": self.design,
            },
            run_id=sample_run_id,
            emit_event=emit,
        )

        start_event = next(e for e in events if e.event_type == EventType.AGENT_START)
        assert start_event.agent == AgentName.DEVELOPER

    @pytest.mark.asyncio
    async def test_agent_complete_event_carries_token_usage(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        response = _make_response(_code_output_payload())
        response.usage.input_tokens = 600
        response.usage.output_tokens = 1200
        self.mock_client.messages.create = AsyncMock(return_value=response)

        await self.agent.execute(
            context={
                "finalized_config": valid_finalized_config,
                "technical_design": self.design,
            },
            run_id=sample_run_id,
            emit_event=emit,
        )

        complete_event = next(e for e in events if e.event_type == EventType.AGENT_COMPLETE)
        assert complete_event.tokens_used is not None
        assert complete_event.tokens_used.input_tokens == 600
        assert complete_event.tokens_used.output_tokens == 1200

    @pytest.mark.asyncio
    async def test_double_failure_emits_error_event_not_agent_complete(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(
                {"reasoning": "ok", "project_name": "x", "files": [], "setup_instructions": "x", "features_implemented": []}
            )
        )

        with pytest.raises(ValueError):
            await self.agent.execute(
                context={
                    "finalized_config": valid_finalized_config,
                    "technical_design": self.design,
                },
                run_id=sample_run_id,
                emit_event=emit,
            )

        types = _event_types(events)
        assert EventType.ERROR in types
        assert EventType.AGENT_COMPLETE not in types


# ===========================================================================
# 3. QA Reviewer
# ===========================================================================

class TestQAReviewerInit:
    """__init__() wires the correct name, schema, and non-empty system prompt."""

    def test_agent_name_is_qa_reviewer(self, mock_anthropic):
        agent = QAReviewer()
        assert agent.name == AgentName.QA_REVIEWER

    def test_output_schema_is_qa_review(self, mock_anthropic):
        agent = QAReviewer()
        assert agent.output_schema is QAReview

    def test_system_prompt_is_non_empty(self, mock_anthropic):
        agent = QAReviewer()
        assert len(agent.system_prompt) > 100

    def test_system_prompt_mentions_qa_reviewer(self, mock_anthropic):
        agent = QAReviewer()
        assert "QA Reviewer" in agent.system_prompt


class TestQAReviewerBuildUserPrompt:
    """build_user_prompt() — single mode (QA Reviewer has no revision branch)."""

    @pytest.fixture(autouse=True)
    def _agent(self, mock_anthropic):
        self.agent = QAReviewer()
        self.design = TechnicalDesign.model_validate(_technical_design_payload())
        self.code = CodeOutput.model_validate(_code_output_payload())

    def test_prompt_contains_review_header(
        self, valid_finalized_config: FinalizedConfig
    ):
        context = {
            "finalized_config": valid_finalized_config,
            "technical_design": self.design,
            "code_output": self.code,
        }
        prompt = self.agent.build_user_prompt(context)
        assert "REVIEW THE IMPLEMENTATION" in prompt

    def test_prompt_contains_customer_requirements_section(
        self, valid_finalized_config: FinalizedConfig
    ):
        context = {
            "finalized_config": valid_finalized_config,
            "technical_design": self.design,
            "code_output": self.code,
        }
        prompt = self.agent.build_user_prompt(context)
        assert "CUSTOMER REQUIREMENTS" in prompt

    def test_prompt_contains_technical_design_section(
        self, valid_finalized_config: FinalizedConfig
    ):
        context = {
            "finalized_config": valid_finalized_config,
            "technical_design": self.design,
            "code_output": self.code,
        }
        prompt = self.agent.build_user_prompt(context)
        assert "TECHNICAL DESIGN" in prompt

    def test_prompt_contains_code_implementation_section(
        self, valid_finalized_config: FinalizedConfig
    ):
        context = {
            "finalized_config": valid_finalized_config,
            "technical_design": self.design,
            "code_output": self.code,
        }
        prompt = self.agent.build_user_prompt(context)
        assert "CODE IMPLEMENTATION" in prompt

    def test_prompt_contains_business_name_from_config(
        self, valid_finalized_config: FinalizedConfig
    ):
        context = {
            "finalized_config": valid_finalized_config,
            "technical_design": self.design,
            "code_output": self.code,
        }
        prompt = self.agent.build_user_prompt(context)
        assert "Cafe Latte" in prompt

    def test_prompt_contains_project_name_from_design(
        self, valid_finalized_config: FinalizedConfig
    ):
        context = {
            "finalized_config": valid_finalized_config,
            "technical_design": self.design,
            "code_output": self.code,
        }
        prompt = self.agent.build_user_prompt(context)
        assert "cafe-latte-ordering" in prompt

    def test_prompt_contains_code_file_path(
        self, valid_finalized_config: FinalizedConfig
    ):
        context = {
            "finalized_config": valid_finalized_config,
            "technical_design": self.design,
            "code_output": self.code,
        }
        prompt = self.agent.build_user_prompt(context)
        assert "app/api/menu/route.js" in prompt

    def test_prompt_contains_api_endpoint_path(
        self, valid_finalized_config: FinalizedConfig
    ):
        context = {
            "finalized_config": valid_finalized_config,
            "technical_design": self.design,
            "code_output": self.code,
        }
        prompt = self.agent.build_user_prompt(context)
        assert "/api/menu" in prompt


class TestQAReviewerExecute:
    """execute() with mocked LLM — all three verdicts, retry, double failure."""

    @pytest.fixture(autouse=True)
    def _agent(self, mock_anthropic):
        self.agent = QAReviewer()
        self.mock_client = mock_anthropic
        self.design = TechnicalDesign.model_validate(_technical_design_payload())
        self.code = CodeOutput.model_validate(_code_output_payload())

    def _context(self, valid_finalized_config: FinalizedConfig) -> dict:
        return {
            "finalized_config": valid_finalized_config,
            "technical_design": self.design,
            "code_output": self.code,
        }

    @pytest.mark.asyncio
    async def test_execute_returns_qa_review_on_valid_response(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(_qa_review_payload("approve"))
        )

        result = await self.agent.execute(
            context=self._context(valid_finalized_config),
            run_id=sample_run_id,
            emit_event=emit,
        )

        assert isinstance(result, QAReview)

    @pytest.mark.asyncio
    async def test_execute_approve_verdict_is_approve_enum(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(_qa_review_payload("approve"))
        )

        result = await self.agent.execute(
            context=self._context(valid_finalized_config),
            run_id=sample_run_id,
            emit_event=emit,
        )

        assert result.verdict == ReviewVerdict.APPROVE

    @pytest.mark.asyncio
    async def test_execute_revise_code_verdict_is_revise_code_enum(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(_qa_review_with_issues_payload("revise_code"))
        )

        result = await self.agent.execute(
            context=self._context(valid_finalized_config),
            run_id=sample_run_id,
            emit_event=emit,
        )

        assert result.verdict == ReviewVerdict.REVISE_CODE

    @pytest.mark.asyncio
    async def test_execute_revise_design_verdict_is_revise_design_enum(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(_qa_review_with_issues_payload("revise_design"))
        )

        result = await self.agent.execute(
            context=self._context(valid_finalized_config),
            run_id=sample_run_id,
            emit_event=emit,
        )

        assert result.verdict == ReviewVerdict.REVISE_DESIGN

    @pytest.mark.asyncio
    async def test_execute_result_has_correct_code_quality_score(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(_qa_review_payload("approve"))
        )

        result = await self.agent.execute(
            context=self._context(valid_finalized_config),
            run_id=sample_run_id,
            emit_event=emit,
        )

        assert result.code_quality_score == 4

    @pytest.mark.asyncio
    async def test_execute_result_has_requirements_coverage_map(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(_qa_review_payload("approve"))
        )

        result = await self.agent.execute(
            context=self._context(valid_finalized_config),
            run_id=sample_run_id,
            emit_event=emit,
        )

        assert isinstance(result.requirements_coverage, dict)
        assert result.requirements_coverage["Menu display with categories"] is True

    @pytest.mark.asyncio
    async def test_execute_revise_code_result_has_one_issue(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(_qa_review_with_issues_payload("revise_code"))
        )

        result = await self.agent.execute(
            context=self._context(valid_finalized_config),
            run_id=sample_run_id,
            emit_event=emit,
        )

        assert len(result.issues) == 1
        assert result.issues[0].id == "issue-1"

    @pytest.mark.asyncio
    async def test_execute_retries_on_schema_validation_failure(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        # code_quality_score outside ge=1, le=5 → ValidationError
        invalid_payload = {
            "reasoning": "ok",
            "verdict": "approve",
            "issues": [],
            "requirements_coverage": {},
            "code_quality_score": 0,  # violates ge=1
            "summary": "ok",
        }
        self.mock_client.messages.create = AsyncMock(
            side_effect=[
                _make_response(invalid_payload),
                _make_response(_qa_review_payload("approve")),
            ]
        )

        result = await self.agent.execute(
            context=self._context(valid_finalized_config),
            run_id=sample_run_id,
            emit_event=emit,
        )

        assert isinstance(result, QAReview)
        assert self.mock_client.messages.create.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_raises_value_error_after_double_schema_failure(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        invalid_payload = {
            "reasoning": "ok",
            "verdict": "approve",
            "issues": [],
            "requirements_coverage": {},
            "code_quality_score": 6,  # violates le=5, always fails
            "summary": "ok",
        }
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(invalid_payload)
        )

        with pytest.raises(ValueError, match="failed output validation after retry"):
            await self.agent.execute(
                context=self._context(valid_finalized_config),
                run_id=sample_run_id,
                emit_event=emit,
            )

        assert self.mock_client.messages.create.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_handles_markdown_json_fences(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        raw_json = json.dumps(_qa_review_payload("approve"))
        content_block = MagicMock()
        content_block.text = f"```json\n{raw_json}\n```"
        usage = MagicMock()
        usage.input_tokens = 100
        usage.output_tokens = 200
        fenced_response = MagicMock()
        fenced_response.content = [content_block]
        fenced_response.usage = usage
        self.mock_client.messages.create = AsyncMock(return_value=fenced_response)

        result = await self.agent.execute(
            context=self._context(valid_finalized_config),
            run_id=sample_run_id,
            emit_event=emit,
        )

        assert isinstance(result, QAReview)

    @pytest.mark.asyncio
    async def test_execute_approve_result_has_empty_issues_list(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(_qa_review_payload("approve"))
        )

        result = await self.agent.execute(
            context=self._context(valid_finalized_config),
            run_id=sample_run_id,
            emit_event=emit,
        )

        assert result.issues == []


class TestQAReviewerEventEmission:
    """Verifies AGENT_START and AGENT_COMPLETE events for QA Reviewer."""

    @pytest.fixture(autouse=True)
    def _agent(self, mock_anthropic):
        self.agent = QAReviewer()
        self.mock_client = mock_anthropic
        self.design = TechnicalDesign.model_validate(_technical_design_payload())
        self.code = CodeOutput.model_validate(_code_output_payload())

    def _context(self, valid_finalized_config: FinalizedConfig) -> dict:
        return {
            "finalized_config": valid_finalized_config,
            "technical_design": self.design,
            "code_output": self.code,
        }

    @pytest.mark.asyncio
    async def test_emits_agent_start_event(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(_qa_review_payload("approve"))
        )

        await self.agent.execute(
            context=self._context(valid_finalized_config),
            run_id=sample_run_id,
            emit_event=emit,
        )

        types = _event_types(events)
        assert EventType.AGENT_START in types

    @pytest.mark.asyncio
    async def test_emits_agent_complete_event(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(_qa_review_payload("approve"))
        )

        await self.agent.execute(
            context=self._context(valid_finalized_config),
            run_id=sample_run_id,
            emit_event=emit,
        )

        types = _event_types(events)
        assert EventType.AGENT_COMPLETE in types

    @pytest.mark.asyncio
    async def test_agent_start_is_emitted_before_agent_complete(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(_qa_review_payload("approve"))
        )

        await self.agent.execute(
            context=self._context(valid_finalized_config),
            run_id=sample_run_id,
            emit_event=emit,
        )

        types = _event_types(events)
        assert types.index(EventType.AGENT_START) < types.index(EventType.AGENT_COMPLETE)

    @pytest.mark.asyncio
    async def test_agent_start_event_has_correct_agent_name(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(_qa_review_payload("approve"))
        )

        await self.agent.execute(
            context=self._context(valid_finalized_config),
            run_id=sample_run_id,
            emit_event=emit,
        )

        start_event = next(e for e in events if e.event_type == EventType.AGENT_START)
        assert start_event.agent == AgentName.QA_REVIEWER

    @pytest.mark.asyncio
    async def test_agent_start_event_has_correct_run_id(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(_qa_review_payload("approve"))
        )

        await self.agent.execute(
            context=self._context(valid_finalized_config),
            run_id=sample_run_id,
            emit_event=emit,
        )

        start_event = next(e for e in events if e.event_type == EventType.AGENT_START)
        assert start_event.run_id == sample_run_id

    @pytest.mark.asyncio
    async def test_agent_complete_event_carries_token_usage(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        response = _make_response(_qa_review_payload("approve"))
        response.usage.input_tokens = 800
        response.usage.output_tokens = 350
        self.mock_client.messages.create = AsyncMock(return_value=response)

        await self.agent.execute(
            context=self._context(valid_finalized_config),
            run_id=sample_run_id,
            emit_event=emit,
        )

        complete_event = next(e for e in events if e.event_type == EventType.AGENT_COMPLETE)
        assert complete_event.tokens_used is not None
        assert complete_event.tokens_used.input_tokens == 800
        assert complete_event.tokens_used.output_tokens == 350

    @pytest.mark.asyncio
    async def test_agent_complete_event_has_non_negative_duration(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(_qa_review_payload("approve"))
        )

        await self.agent.execute(
            context=self._context(valid_finalized_config),
            run_id=sample_run_id,
            emit_event=emit,
        )

        complete_event = next(e for e in events if e.event_type == EventType.AGENT_COMPLETE)
        assert complete_event.duration_ms is not None
        assert complete_event.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_full_event_sequence_is_ordered(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        """AGENT_START → LLM_CALL_START → LLM_CALL_COMPLETE → AGENT_COMPLETE."""
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(_qa_review_payload("approve"))
        )

        await self.agent.execute(
            context=self._context(valid_finalized_config),
            run_id=sample_run_id,
            emit_event=emit,
        )

        types = _event_types(events)
        assert types.index(EventType.AGENT_START) < types.index(EventType.LLM_CALL_START)
        assert types.index(EventType.LLM_CALL_START) < types.index(EventType.LLM_CALL_COMPLETE)
        assert types.index(EventType.LLM_CALL_COMPLETE) < types.index(EventType.AGENT_COMPLETE)

    @pytest.mark.asyncio
    async def test_double_failure_emits_error_event(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        invalid_payload = {
            "reasoning": "ok",
            "verdict": "approve",
            "issues": [],
            "requirements_coverage": {},
            "code_quality_score": 6,
            "summary": "ok",
        }
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(invalid_payload)
        )

        with pytest.raises(ValueError):
            await self.agent.execute(
                context=self._context(valid_finalized_config),
                run_id=sample_run_id,
                emit_event=emit,
            )

        types = _event_types(events)
        assert EventType.ERROR in types
        assert EventType.AGENT_COMPLETE not in types

    @pytest.mark.asyncio
    async def test_double_failure_error_event_has_error_and_raw_output_in_data(
        self,
        valid_finalized_config: FinalizedConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        invalid_payload = {
            "reasoning": "ok",
            "verdict": "approve",
            "issues": [],
            "requirements_coverage": {},
            "code_quality_score": 6,
            "summary": "ok",
        }
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(invalid_payload)
        )

        with pytest.raises(ValueError):
            await self.agent.execute(
                context=self._context(valid_finalized_config),
                run_id=sample_run_id,
                emit_event=emit,
            )

        error_event = next(e for e in events if e.event_type == EventType.ERROR)
        assert "error" in error_event.data
        assert "raw_output" not in error_event.data
