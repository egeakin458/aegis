"""
Integration test — full pipeline from CustomerConfigV2 (DDC) to COMPLETE.

Runs the complete Aegis pipeline with mocked LLM responses, verifying
that all 4 agents execute in sequence, context flows correctly, events
are emitted, and the pipeline reaches COMPLETE with a valid outcome.

This does NOT call a real LLM. Each agent's LLM response is pre-canned
JSON matching the expected output schema.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents import Developer, QAReviewer, RequirementsAnalyst, SolutionArchitect
from app.pipeline.runner import PipelineRunner
from app.schemas.agent_outputs import BuildCheckResult
from app.schemas.pipeline_events import EventType, PipelineState


@pytest.fixture(autouse=True)
def mock_build_check_pass():
    """Patch run_build_check to return a passing result for integration tests."""
    passing = BuildCheckResult(passed=True, duration_ms=5, files_checked=4)
    with patch("app.pipeline.runner.run_build_check", new=AsyncMock(return_value=passing)):
        yield


def _ra_response(ddc_dict: dict) -> dict:
    return {
        "needs_clarification": False,
        "reasoning": "DDC validated and complete.",
        "finalized_config": ddc_dict,
    }


SA_RESPONSE = {
    "reasoning": "DDC mapping applied: one DataModel per Entity, one APIEndpoint per UseCase.",
    "project_name": "shopflow",
    "tech_summary": "Next.js 14 with App Router, Tailwind CSS, better-sqlite3",
    "data_models": [
        {
            "name": "Product",
            "description": "A product available for sale",
            "fields": [
                {"name": "title", "type": "string", "required": True},
                {"name": "price", "type": "float", "required": True},
                {"name": "stock", "type": "integer", "required": True},
            ],
            "relationships": [],
        },
        {
            "name": "Order",
            "description": "A customer order",
            "fields": [
                {"name": "total", "type": "float", "required": True},
                {"name": "state", "type": "string", "required": True},
            ],
            "relationships": [],
        },
    ],
    "api_endpoints": [
        {
            "method": "GET",
            "path": "/api/products",
            "description": "List all products",
            "response": "Array of Product objects",
            "feature_id": "uc_browse_products",
        },
        {
            "method": "POST",
            "path": "/api/orders",
            "description": "Place an order",
            "response": "Created Order object",
            "feature_id": "uc_place_order",
        },
        {
            "method": "POST",
            "path": "/api/admin/products",
            "description": "Manage products",
            "response": "Product object",
            "feature_id": "uc_manage_catalog",
        },
        {
            "method": "GET",
            "path": "/api/admin/orders",
            "description": "List all orders",
            "response": "Array of Order objects",
            "feature_id": "uc_view_orders",
        },
    ],
    "ui_components": [
        {
            "name": "ProductsPage",
            "type": "page",
            "description": "Lists products for browsing",
            "features": ["Browse products"],
            "data_sources": ["/api/products"],
        },
    ],
    "file_structure": [
        {"path": "app/page.js", "purpose": "Home page"},
        {"path": "app/api/products/route.js", "purpose": "Products API"},
        {"path": "lib/db.js", "purpose": "DB setup"},
    ],
    "dependencies": ["next", "tailwindcss", "better-sqlite3"],
}


DEV_RESPONSE = {
    "reasoning": "Implemented all use cases following the technical design.",
    "project_name": "shopflow",
    "files": [
        {
            "path": "app/page.js",
            "content": "export default function Home() { return <div className='p-4'>Home</div>; }",
            "language": "javascript",
            "description": "Home page",
        },
        {
            "path": "app/api/products/route.js",
            "content": "import { NextResponse } from 'next/server';\nexport async function GET() { return NextResponse.json([]); }",
            "language": "javascript",
            "description": "Products API",
        },
        {
            "path": "lib/db.js",
            "content": "import Database from 'better-sqlite3';\nexport const db = new Database('app.db');",
            "language": "javascript",
            "description": "DB setup",
        },
    ],
    "setup_instructions": "npm install && npm run dev",
    "features_implemented": [
        {"feature_id": "uc_browse_products", "description": "Browse products", "implementation_notes": None},
        {"feature_id": "uc_place_order", "description": "Place order", "implementation_notes": None},
        {"feature_id": "uc_manage_catalog", "description": "Manage product catalog", "implementation_notes": None},
        {"feature_id": "uc_view_orders", "description": "View all orders", "implementation_notes": None},
    ],
    "known_limitations": [],
}


QA_RESPONSE = {
    "reasoning": "Per-rule check: 'Stock check': enforced=yes — handled in /api/orders POST. All use cases implemented.",
    "verdict": "approve",
    "issues": [],
    "requirements_coverage": [
        {"feature_id": "uc_browse_products", "implemented": True, "evidence": "/api/products"},
        {"feature_id": "uc_place_order", "implemented": True, "evidence": "/api/orders"},
        {"feature_id": "uc_manage_catalog", "implemented": True, "evidence": "/api/admin/products"},
        {"feature_id": "uc_view_orders", "implemented": True, "evidence": "/api/admin/orders"},
    ],
    "code_quality_score": 4,
    "summary": "Your ordering application is ready.",
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


def _build_pipeline_with_mocked_llm(ddc_dict: dict) -> tuple[PipelineRunner, list]:
    """Build a full pipeline with real agents but mocked LLM clients."""
    ra = RequirementsAnalyst()
    sa = SolutionArchitect()
    dev = Developer()
    qa = QAReviewer()

    ra.client = MagicMock()
    ra.client.messages.create = AsyncMock(return_value=_mock_llm_response(_ra_response(ddc_dict)))

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

    events: list = []
    runner = PipelineRunner(agents=agents, emit_event=events.append)
    return runner, events


class TestDDCFullPipelineIntegration:
    """End-to-end DDC pipeline run: CustomerConfigV2 → COMPLETE."""

    @pytest.fixture(autouse=True)
    def _mock_anthropic(self, mock_anthropic):
        # mock_anthropic auto-patches the AsyncAnthropic constructor used by agents
        pass

    @pytest.mark.asyncio
    async def test_pipeline_reaches_complete(self, ddc_ecommerce):
        ddc_dict = ddc_ecommerce.model_dump(mode="json")
        runner, events = _build_pipeline_with_mocked_llm(ddc_dict)
        result = await runner.run(ddc_ecommerce)
        assert result.state == PipelineState.COMPLETE
        assert result.outcome == "success"

    @pytest.mark.asyncio
    async def test_pipeline_emits_terminal_event(self, ddc_ecommerce):
        ddc_dict = ddc_ecommerce.model_dump(mode="json")
        runner, events = _build_pipeline_with_mocked_llm(ddc_dict)
        await runner.run(ddc_ecommerce)
        event_types = [e.event_type for e in events]
        assert EventType.PIPELINE_COMPLETE in event_types

    @pytest.mark.asyncio
    async def test_pipeline_emits_pipeline_started_first(self, ddc_ecommerce):
        ddc_dict = ddc_ecommerce.model_dump(mode="json")
        runner, events = _build_pipeline_with_mocked_llm(ddc_dict)
        await runner.run(ddc_ecommerce)
        assert events[0].event_type == EventType.PIPELINE_STARTED

    @pytest.mark.asyncio
    async def test_context_contains_customer_config_v2(self, ddc_ecommerce):
        ddc_dict = ddc_ecommerce.model_dump(mode="json")
        runner, events = _build_pipeline_with_mocked_llm(ddc_dict)
        await runner.run(ddc_ecommerce)
        assert "customer_config_v2" in runner.context
        assert "technical_design" in runner.context
        assert "code_output" in runner.context
