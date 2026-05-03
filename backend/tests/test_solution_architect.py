"""
Tests for the Solution Architect agent — DDC mode.

Coverage:
  1. SolutionArchitect.build_user_prompt() — DDC branch includes feature_id instruction
  2. SolutionArchitect.execute() — golden DDC in, one endpoint per use case,
     one data model per entity, feature_id threaded correctly
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.solution_architect import SolutionArchitect
from app.schemas.agent_outputs import TechnicalDesign, APIEndpoint, DataModel
from app.schemas.customer_config_v2 import CustomerConfigV2
from app.schemas.pipeline_events import EventType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_technical_design(
    data_models: list[dict],
    api_endpoints: list[dict],
) -> dict:
    return {
        "reasoning": "DDC mapping applied.",
        "project_name": "shopflow",
        "tech_summary": "Next.js 14, Tailwind CSS, better-sqlite3.",
        "data_models": data_models,
        "api_endpoints": api_endpoints,
        "ui_components": [
            {
                "name": "ProductPage",
                "type": "page",
                "description": "Browse and manage products.",
                "features": ["Browse Products"],
                "data_sources": ["/api/products"],
            }
        ],
        "file_structure": [
            {"path": "app/page.js", "purpose": "Home dashboard"},
            {"path": "app/api/products/route.js", "purpose": "Product endpoints"},
            {"path": "lib/db.js", "purpose": "Database connection"},
            {"path": "package.json", "purpose": "Dependencies"},
        ],
        "dependencies": ["next", "tailwindcss", "better-sqlite3", "postcss", "autoprefixer"],
        "notes": "Business rules enforced server-side.",
    }


def _make_sa_response(payload: dict) -> MagicMock:
    content_block = MagicMock()
    content_block.text = json.dumps(payload)
    usage = MagicMock()
    usage.input_tokens = 300
    usage.output_tokens = 800
    response = MagicMock()
    response.content = [content_block]
    response.usage = usage
    return response


def _make_agent() -> SolutionArchitect:
    return SolutionArchitect()


# ---------------------------------------------------------------------------
# Sync tests — prompt and schema
# ---------------------------------------------------------------------------

class TestDDCSASync:
    """Sync tests for SA DDC prompt and APIEndpoint schema."""

    @pytest.fixture(autouse=True)
    def patch_use_ddc(self, monkeypatch):
        monkeypatch.setattr("app.agents.solution_architect.settings.use_ddc", True)
        monkeypatch.setattr("app.config.settings.use_ddc", True)

    def test_ddc_system_prompt_mentions_feature_id(self):
        agent = _make_agent()
        assert "feature_id" in agent.system_prompt

    def test_ddc_system_prompt_mentions_use_case_id(self):
        agent = _make_agent()
        assert "use_case.id" in agent.system_prompt

    def test_ddc_system_prompt_mentions_mandatory_mapping(self):
        agent = _make_agent()
        assert "MANDATORY" in agent.system_prompt or "mandatory" in agent.system_prompt.lower()

    def test_ddc_user_prompt_contains_ddc_input(self, ddc_ecommerce: CustomerConfigV2):
        agent = _make_agent()
        prompt = agent.build_user_prompt({"customer_config_v2": ddc_ecommerce})
        assert "shopflow" in prompt
        assert "feature_id" in prompt

    def test_ddc_user_prompt_not_legacy_format(self, ddc_ecommerce: CustomerConfigV2):
        agent = _make_agent()
        prompt = agent.build_user_prompt({"customer_config_v2": ddc_ecommerce})
        assert "FINALIZED REQUIREMENTS" not in prompt
        assert "DDC INPUT" in prompt

    def test_api_endpoint_feature_id_optional(self):
        ep = APIEndpoint(
            method="GET", path="/api/products",
            description="List products", response="Product list",
        )
        assert ep.feature_id is None

    def test_api_endpoint_feature_id_set(self):
        ep = APIEndpoint(
            method="GET", path="/api/products",
            description="List products", response="Product list",
            feature_id="uc_browse01",
        )
        assert ep.feature_id == "uc_browse01"


# ---------------------------------------------------------------------------
# Async tests — execute()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestDDC:
    """Async execute() tests for SA in DDC mode."""

    @pytest.fixture(autouse=True)
    def patch_use_ddc(self, monkeypatch):
        monkeypatch.setattr("app.agents.solution_architect.settings.use_ddc", True)
        monkeypatch.setattr("app.config.settings.use_ddc", True)

    def _design_matching_golden(self, ddc: CustomerConfigV2) -> dict:
        """Build a TechnicalDesign dict that mirrors the golden fixture's entities/use cases."""
        data_models = [
            {
                "name": e.name,
                "description": f"Stores {e.name} records.",
                "fields": [
                    {"name": a.name, "type": "string", "required": a.required,
                     "description": None, "constraints": None}
                    for a in e.attributes
                ],
                "relationships": [],
            }
            for e in ddc.entities
        ]
        api_endpoints = [
            {
                "method": "GET" if uc.type == "query" else "POST",
                "path": f"/api/{uc.name.lower().replace(' ', '-')}",
                "description": uc.name,
                "request_body": None,
                "response": "JSON response",
                "feature_id": uc.id,
            }
            for uc in ddc.use_cases
        ]
        return _make_technical_design(data_models, api_endpoints)

    async def test_one_data_model_per_entity(
        self, mock_anthropic, ddc_ecommerce: CustomerConfigV2, sample_run_id, captured_events
    ):
        agent = _make_agent()
        design_dict = self._design_matching_golden(ddc_ecommerce)
        mock_anthropic.messages.create = AsyncMock(
            return_value=_make_sa_response(design_dict)
        )
        events, emit = captured_events
        result: TechnicalDesign = await agent.execute(
            context={"customer_config_v2": ddc_ecommerce},
            run_id=sample_run_id,
            emit_event=emit,
        )
        assert isinstance(result, TechnicalDesign)
        entity_names = {e.name for e in ddc_ecommerce.entities}
        model_names = {m.name for m in result.data_models}
        assert entity_names == model_names, (
            f"Expected one DataModel per entity. Missing: {entity_names - model_names}"
        )

    async def test_one_endpoint_per_use_case(
        self, mock_anthropic, ddc_ecommerce: CustomerConfigV2, sample_run_id, captured_events
    ):
        agent = _make_agent()
        design_dict = self._design_matching_golden(ddc_ecommerce)
        mock_anthropic.messages.create = AsyncMock(
            return_value=_make_sa_response(design_dict)
        )
        events, emit = captured_events
        result: TechnicalDesign = await agent.execute(
            context={"customer_config_v2": ddc_ecommerce},
            run_id=sample_run_id,
            emit_event=emit,
        )
        assert len(result.api_endpoints) == len(ddc_ecommerce.use_cases), (
            f"Expected {len(ddc_ecommerce.use_cases)} endpoints, "
            f"got {len(result.api_endpoints)}"
        )

    async def test_feature_ids_match_use_case_ids(
        self, mock_anthropic, ddc_ecommerce: CustomerConfigV2, sample_run_id, captured_events
    ):
        agent = _make_agent()
        design_dict = self._design_matching_golden(ddc_ecommerce)
        mock_anthropic.messages.create = AsyncMock(
            return_value=_make_sa_response(design_dict)
        )
        events, emit = captured_events
        result: TechnicalDesign = await agent.execute(
            context={"customer_config_v2": ddc_ecommerce},
            run_id=sample_run_id,
            emit_event=emit,
        )
        uc_ids = {uc.id for uc in ddc_ecommerce.use_cases}
        endpoint_feature_ids = {ep.feature_id for ep in result.api_endpoints if ep.feature_id}
        assert endpoint_feature_ids == uc_ids, (
            f"feature_id mismatch. UC ids: {uc_ids}, endpoint ids: {endpoint_feature_ids}"
        )

    async def test_agent_complete_event_emitted(
        self, mock_anthropic, ddc_ecommerce: CustomerConfigV2, sample_run_id, captured_events
    ):
        agent = _make_agent()
        design_dict = self._design_matching_golden(ddc_ecommerce)
        mock_anthropic.messages.create = AsyncMock(
            return_value=_make_sa_response(design_dict)
        )
        events, emit = captured_events
        await agent.execute(
            context={"customer_config_v2": ddc_ecommerce},
            run_id=sample_run_id,
            emit_event=emit,
        )
        types = [e.event_type for e in events]
        assert EventType.AGENT_START in types
        assert EventType.AGENT_COMPLETE in types

    async def test_design_revision_prompt_includes_qa_feedback(
        self, mock_anthropic, ddc_ecommerce: CustomerConfigV2, sample_run_id, captured_events
    ):
        """In revision mode the prompt must include previous design and QA feedback."""
        agent = _make_agent()
        design_dict = self._design_matching_golden(ddc_ecommerce)
        mock_anthropic.messages.create = AsyncMock(
            return_value=_make_sa_response(design_dict)
        )
        previous_design = TechnicalDesign(**design_dict)
        qa_review_mock = MagicMock()
        qa_review_mock.model_dump = MagicMock(
            return_value={"verdict": "revise_design", "issues": []}
        )
        events, emit = captured_events

        # Capture the prompt that would be sent
        captured_prompts = []
        original_call = agent._call_llm

        async def capture_prompt(user_prompt, *args, **kwargs):
            captured_prompts.append(user_prompt)
            return await original_call(user_prompt, *args, **kwargs)

        agent._call_llm = capture_prompt
        await agent.execute(
            context={
                "customer_config_v2": ddc_ecommerce,
                "previous_design": previous_design,
                "qa_review": qa_review_mock,
            },
            run_id=sample_run_id,
            emit_event=emit,
        )
        assert len(captured_prompts) == 1
        assert "DESIGN REVISION" in captured_prompts[0]
        assert "QA FEEDBACK" in captured_prompts[0]
