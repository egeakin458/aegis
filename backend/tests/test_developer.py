"""
Tests for the Developer agent — DDC mode.

Coverage:
  1. DDC system prompt enforces SQL type mapping and feature_id threading
  2. build_user_prompt() — DDC branch contains DDC input, not legacy format
  3. execute() — FeatureImplementation.feature_id round-trips from use_case.id
  4. execute() — package.json in generated files lists better-sqlite3 and next@14
  5. execute() — revision mode produces CodePatch in DDC mode
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.developer import Developer
from app.schemas.agent_outputs import (
    CodeOutput,
    CodePatch,
    TechnicalDesign,
    APIEndpoint,
    DataModel,
    DataField,
    UIComponent,
    FileSpec,
)
from app.schemas.customer_config_v2 import CustomerConfigV2
from app.schemas.pipeline_events import EventType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_technical_design_from_ddc(ddc: CustomerConfigV2) -> TechnicalDesign:
    """Build a minimal TechnicalDesign that mirrors the golden DDC."""
    data_models = [
        DataModel(
            name=e.name,
            description=f"Stores {e.name} data.",
            fields=[DataField(name=a.name, type="string") for a in e.attributes],
        )
        for e in ddc.entities
    ]
    api_endpoints = [
        APIEndpoint(
            method="GET" if uc.type == "query" else "POST",
            path=f"/api/{uc.name.lower().replace(' ', '-')}",
            description=uc.name,
            response="JSON",
            feature_id=uc.id,
        )
        for uc in ddc.use_cases
    ]
    return TechnicalDesign(
        reasoning="DDC-driven design.",
        project_name="shopflow",
        tech_summary="Next.js 14, Tailwind, better-sqlite3.",
        data_models=data_models,
        api_endpoints=api_endpoints,
        ui_components=[
            UIComponent(
                name="HomePage",
                type="page",
                description="Main page.",
                features=["Browse"],
                data_sources=["/api/browse-products"],
            )
        ],
        file_structure=[
            FileSpec(path="package.json", purpose="Dependencies"),
            FileSpec(path="app/page.js", purpose="Home"),
            FileSpec(path="lib/db.js", purpose="Database"),
        ],
        dependencies=["next", "tailwindcss", "better-sqlite3", "postcss", "autoprefixer"],
    )


def _make_package_json_content(ddc: CustomerConfigV2) -> str:
    return json.dumps({
        "name": "shopflow",
        "version": "0.1.0",
        "dependencies": {
            "next": "14.2.3",
            "better-sqlite3": "^9.0.0",
            "tailwindcss": "^3.4.0",
            "postcss": "^8.4.0",
            "autoprefixer": "^10.4.0",
        },
        "scripts": {"dev": "next dev", "build": "next build"},
    })


def _make_code_output(ddc: CustomerConfigV2) -> dict:
    features = [
        {
            "feature_id": uc.id,
            "description": uc.name,
            "implementation_notes": None,
        }
        for uc in ddc.use_cases
    ]
    return {
        "reasoning": "Implemented per DDC.",
        "project_name": "shopflow",
        "files": [
            {
                "path": "package.json",
                "content": _make_package_json_content(ddc),
                "language": "json",
                "description": "Project dependencies.",
            },
            {
                "path": "app/page.js",
                "content": "export default function Home() { return <main>Hello</main>; }",
                "language": "javascript",
                "description": "Home page.",
            },
            {
                "path": "lib/db.js",
                "content": "const Database = require('better-sqlite3'); module.exports = new Database('app.db');",
                "language": "javascript",
                "description": "Database connection.",
            },
        ],
        "setup_instructions": "npm install && npm run dev",
        "features_implemented": features,
        "known_limitations": [],
    }


def _make_dev_response(payload: dict) -> MagicMock:
    content_block = MagicMock()
    content_block.text = json.dumps(payload)
    usage = MagicMock()
    usage.input_tokens = 400
    usage.output_tokens = 1200
    response = MagicMock()
    response.content = [content_block]
    response.usage = usage
    return response


# ---------------------------------------------------------------------------
# Sync tests
# ---------------------------------------------------------------------------

class TestDDCDevSync:
    """Sync tests for Developer DDC prompt."""

    @pytest.fixture(autouse=True)
    def patch_use_ddc(self, monkeypatch):
        monkeypatch.setattr("app.agents.developer.settings.use_ddc", True)
        monkeypatch.setattr("app.config.settings.use_ddc", True)

    def _make_agent(self) -> Developer:
        return Developer()

    def test_ddc_system_prompt_mentions_sql_type_mapping(self):
        agent = self._make_agent()
        assert "decimal" in agent.system_prompt
        assert "REAL" in agent.system_prompt

    def test_ddc_system_prompt_enforces_feature_id_threading(self):
        agent = self._make_agent()
        assert "use_case.id" in agent.system_prompt
        assert "feature_id" in agent.system_prompt

    def test_ddc_system_prompt_mentions_states_check_constraint(self):
        agent = self._make_agent()
        assert "CHECK" in agent.system_prompt or "states" in agent.system_prompt

    def test_ddc_system_prompt_mentions_next_14(self):
        agent = self._make_agent()
        assert "next" in agent.system_prompt.lower()
        assert "14" in agent.system_prompt
        assert "better-sqlite3" in agent.system_prompt

    def test_ddc_user_prompt_contains_ddc_json(self, ddc_ecommerce: CustomerConfigV2):
        agent = self._make_agent()
        design = _make_technical_design_from_ddc(ddc_ecommerce)
        prompt = agent.build_user_prompt({
            "customer_config_v2": ddc_ecommerce,
            "technical_design": design,
        })
        assert "shopflow" in prompt
        assert "DDC INPUT" in prompt

    def test_ddc_user_prompt_not_legacy_format(self, ddc_ecommerce: CustomerConfigV2):
        agent = self._make_agent()
        design = _make_technical_design_from_ddc(ddc_ecommerce)
        prompt = agent.build_user_prompt({
            "customer_config_v2": ddc_ecommerce,
            "technical_design": design,
        })
        assert "CUSTOMER REQUIREMENTS" not in prompt
        assert "use_case.id" in prompt

    def test_ddc_revision_prompt_uses_codepatch_schema(self, ddc_ecommerce: CustomerConfigV2):
        agent = self._make_agent()
        design = _make_technical_design_from_ddc(ddc_ecommerce)
        previous_code = MagicMock()
        previous_code.model_dump = MagicMock(return_value={})
        qa_review = MagicMock()
        qa_review.model_dump = MagicMock(return_value={"verdict": "revise_code"})
        prompt = agent.build_user_prompt({
            "customer_config_v2": ddc_ecommerce,
            "technical_design": design,
            "previous_code": previous_code,
            "qa_review": qa_review,
        })
        assert "CodePatch" in prompt
        assert "CODE REVISION" in prompt


# ---------------------------------------------------------------------------
# Async tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestDDC:
    """Async execute() tests for Developer in DDC mode."""

    @pytest.fixture(autouse=True)
    def patch_use_ddc(self, monkeypatch):
        monkeypatch.setattr("app.agents.developer.settings.use_ddc", True)
        monkeypatch.setattr("app.config.settings.use_ddc", True)

    def _make_agent(self) -> Developer:
        return Developer()

    async def test_feature_ids_match_use_case_ids(
        self, mock_anthropic, ddc_ecommerce: CustomerConfigV2, sample_run_id, captured_events
    ):
        """FeatureImplementation.feature_id must equal the originating UseCase.id."""
        agent = self._make_agent()
        design = _make_technical_design_from_ddc(ddc_ecommerce)
        code_output = _make_code_output(ddc_ecommerce)
        mock_anthropic.messages.create = AsyncMock(
            return_value=_make_dev_response(code_output)
        )
        events, emit = captured_events
        result: CodeOutput = await agent.execute(
            context={
                "customer_config_v2": ddc_ecommerce,
                "technical_design": design,
            },
            run_id=sample_run_id,
            emit_event=emit,
        )
        assert isinstance(result, CodeOutput)
        uc_ids = {uc.id for uc in ddc_ecommerce.use_cases}
        implemented_ids = {f.feature_id for f in result.features_implemented}
        assert implemented_ids == uc_ids, (
            f"feature_id mismatch. use_case ids: {uc_ids}, "
            f"implemented ids: {implemented_ids}"
        )

    async def test_package_json_includes_better_sqlite3_and_next14(
        self, mock_anthropic, ddc_ecommerce: CustomerConfigV2, sample_run_id, captured_events
    ):
        """Generated package.json must list better-sqlite3 and next@14."""
        agent = self._make_agent()
        design = _make_technical_design_from_ddc(ddc_ecommerce)
        code_output = _make_code_output(ddc_ecommerce)
        mock_anthropic.messages.create = AsyncMock(
            return_value=_make_dev_response(code_output)
        )
        events, emit = captured_events
        result: CodeOutput = await agent.execute(
            context={
                "customer_config_v2": ddc_ecommerce,
                "technical_design": design,
            },
            run_id=sample_run_id,
            emit_event=emit,
        )
        pkg_files = [f for f in result.files if f.path == "package.json"]
        assert pkg_files, "package.json must be present in generated files"
        pkg_content = json.loads(pkg_files[0].content)
        deps = pkg_content.get("dependencies", {})
        assert "better-sqlite3" in deps, "better-sqlite3 must be in package.json dependencies"
        next_version = deps.get("next", "")
        assert next_version.startswith("14"), (
            f"next dependency must be version 14.x, got: {next_version}"
        )

    async def test_revision_mode_produces_code_patch(
        self, mock_anthropic, ddc_ecommerce: CustomerConfigV2, sample_run_id, captured_events
    ):
        """When previous_code is in context, output schema switches to CodePatch."""
        agent = self._make_agent()
        design = _make_technical_design_from_ddc(ddc_ecommerce)
        patch_output = {
            "reasoning": "Fixed the broken endpoint.",
            "files_to_replace": [
                {
                    "path": "app/api/browse-products/route.js",
                    "content": "export async function GET() { return Response.json([]); }",
                    "language": "javascript",
                    "description": "Fixed products route.",
                }
            ],
            "files_to_delete": [],
            "setup_instructions_changed": False,
            "new_setup_instructions": None,
            "features_implemented_delta": [],
        }
        previous_code = MagicMock()
        previous_code.model_dump = MagicMock(return_value={})
        mock_anthropic.messages.create = AsyncMock(
            return_value=_make_dev_response(patch_output)
        )
        events, emit = captured_events
        result = await agent.execute(
            context={
                "customer_config_v2": ddc_ecommerce,
                "technical_design": design,
                "previous_code": previous_code,
            },
            run_id=sample_run_id,
            emit_event=emit,
        )
        assert isinstance(result, CodePatch)
        assert len(result.files_to_replace) == 1

    async def test_agent_complete_event_emitted(
        self, mock_anthropic, ddc_ecommerce: CustomerConfigV2, sample_run_id, captured_events
    ):
        agent = self._make_agent()
        design = _make_technical_design_from_ddc(ddc_ecommerce)
        code_output = _make_code_output(ddc_ecommerce)
        mock_anthropic.messages.create = AsyncMock(
            return_value=_make_dev_response(code_output)
        )
        events, emit = captured_events
        await agent.execute(
            context={
                "customer_config_v2": ddc_ecommerce,
                "technical_design": design,
            },
            run_id=sample_run_id,
            emit_event=emit,
        )
        types = [e.event_type for e in events]
        assert EventType.AGENT_START in types
        assert EventType.AGENT_COMPLETE in types
