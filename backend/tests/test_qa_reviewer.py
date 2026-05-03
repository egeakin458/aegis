"""
Tests for the QA Reviewer agent — DDC mode.

Coverage:
  1. DDC system prompt enforces per-rule checks and use_case.id keying
  2. build_user_prompt() — DDC branch uses DDC INPUT, not legacy format
  3. execute() — requirements_coverage has exactly one entry per use_case.id
  4. execute() — verdict revise_code when entity attribute missing from code
  5. execute() — approve verdict when all use cases covered and rules enforced
  6. execute() — reasoning includes per-rule enforcement text
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.qa_reviewer import QAReviewer
from app.schemas.agent_outputs import (
    QAReview,
    ReviewVerdict,
    TechnicalDesign,
    APIEndpoint,
    DataModel,
    DataField,
    UIComponent,
    FileSpec,
    CodeOutput,
    CodeFile,
    FeatureImplementation,
)
from app.schemas.customer_config import CustomerConfigV2
from app.schemas.pipeline_events import EventType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_technical_design_from_ddc(ddc: CustomerConfigV2) -> TechnicalDesign:
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
        reasoning="DDC design.",
        project_name="shopflow",
        tech_summary="Next.js 14, Tailwind, better-sqlite3.",
        data_models=data_models,
        api_endpoints=api_endpoints,
        ui_components=[
            UIComponent(
                name="HomePage", type="page",
                description="Main page.", features=["Browse"], data_sources=[],
            )
        ],
        file_structure=[
            FileSpec(path="package.json", purpose="Dependencies"),
            FileSpec(path="lib/db.js", purpose="Database"),
        ],
        dependencies=["next", "tailwindcss", "better-sqlite3"],
    )


def _make_code_output(ddc: CustomerConfigV2) -> CodeOutput:
    return CodeOutput(
        reasoning="Implemented per DDC.",
        project_name="shopflow",
        files=[
            CodeFile(
                path="package.json",
                content=json.dumps({
                    "dependencies": {
                        "next": "14.2.3",
                        "better-sqlite3": "^9.0.0",
                        "tailwindcss": "^3.4.0",
                    }
                }),
                language="json",
                description="Dependencies.",
            ),
            CodeFile(
                path="lib/db.js",
                content="const Database = require('better-sqlite3'); module.exports = new Database('app.db');",
                language="javascript",
                description="DB init.",
            ),
        ],
        setup_instructions="npm install && npm run dev",
        features_implemented=[
            FeatureImplementation(feature_id=uc.id, description=uc.name)
            for uc in ddc.use_cases
        ],
        known_limitations=[],
    )


def _make_approve_qa_review(ddc: CustomerConfigV2) -> dict:
    return {
        "reasoning": (
            "All use cases covered. "
            + " ".join(
                f"Rule '{r.description}': enforced=yes — implemented in API layer."
                for r in ddc.business_rules
            )
        ),
        "verdict": "approve",
        "issues": [],
        "requirements_coverage": [
            {"feature_id": uc.id, "implemented": True, "evidence": f"Endpoint at /api/{uc.id}"}
            for uc in ddc.use_cases
        ],
        "code_quality_score": 4,
        "summary": "All features implemented. Application is ready for delivery.",
    }


def _make_revise_code_qa_review(ddc: CustomerConfigV2) -> dict:
    return {
        "reasoning": (
            "Missing entity attribute 'price' in Product table. "
            + " ".join(
                f"Rule '{r.description}': enforced=unclear — not found in code."
                for r in ddc.business_rules
            )
        ),
        "verdict": "revise_code",
        "issues": [
            {
                "id": "issue-missing-attr",
                "severity": "major",
                "category": "functional",
                "affected_file": "lib/schema.sql",
                "description": "Product table is missing the 'price' column defined in the DDC.",
                "suggestion": "Add `price REAL NOT NULL` to the CREATE TABLE Product statement in lib/schema.sql.",
            }
        ],
        "requirements_coverage": [
            {"feature_id": uc.id, "implemented": True, "evidence": "Endpoint found."}
            for uc in ddc.use_cases
        ],
        "code_quality_score": 2,
        "summary": "Some data fields are missing. A fix is needed before delivery.",
    }


def _make_qa_response(payload: dict) -> MagicMock:
    content_block = MagicMock()
    content_block.text = json.dumps(payload)
    usage = MagicMock()
    usage.input_tokens = 350
    usage.output_tokens = 600
    response = MagicMock()
    response.content = [content_block]
    response.usage = usage
    return response


# ---------------------------------------------------------------------------
# Sync tests
# ---------------------------------------------------------------------------

class TestDDCQASync:
    """Sync tests for QA Reviewer DDC prompt."""

    def _make_agent(self) -> QAReviewer:
        return QAReviewer()

    def test_ddc_system_prompt_requires_per_rule_checks(self):
        agent = self._make_agent()
        assert "enforced=yes" in agent.system_prompt or "per-rule" in agent.system_prompt.lower()

    def test_ddc_system_prompt_keys_coverage_by_use_case_id(self):
        agent = self._make_agent()
        assert "use_case.id" in agent.system_prompt

    def test_ddc_system_prompt_checks_entity_attributes(self):
        agent = self._make_agent()
        assert "Attribute" in agent.system_prompt or "attribute" in agent.system_prompt.lower()

    def test_ddc_user_prompt_contains_ddc_input(
        self, ddc_ecommerce: CustomerConfigV2
    ):
        agent = self._make_agent()
        design = _make_technical_design_from_ddc(ddc_ecommerce)
        code = _make_code_output(ddc_ecommerce)
        prompt = agent.build_user_prompt({
            "customer_config_v2": ddc_ecommerce,
            "technical_design": design,
            "code_output": code,
        })
        assert "DDC INPUT" in prompt
        assert "shopflow" in prompt

    def test_ddc_user_prompt_not_legacy_format(
        self, ddc_ecommerce: CustomerConfigV2
    ):
        agent = self._make_agent()
        design = _make_technical_design_from_ddc(ddc_ecommerce)
        code = _make_code_output(ddc_ecommerce)
        prompt = agent.build_user_prompt({
            "customer_config_v2": ddc_ecommerce,
            "technical_design": design,
            "code_output": code,
        })
        assert "CUSTOMER REQUIREMENTS" not in prompt
        assert "use_case.id" in prompt


# ---------------------------------------------------------------------------
# Async tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestDDC:
    """Async execute() tests for QA Reviewer in DDC mode."""

    def _make_agent(self) -> QAReviewer:
        return QAReviewer()

    async def test_coverage_list_matches_use_cases_one_to_one(
        self, mock_anthropic, ddc_ecommerce: CustomerConfigV2, sample_run_id, captured_events
    ):
        """requirements_coverage must have exactly one entry per use_case.id."""
        agent = self._make_agent()
        design = _make_technical_design_from_ddc(ddc_ecommerce)
        code = _make_code_output(ddc_ecommerce)
        qa_payload = _make_approve_qa_review(ddc_ecommerce)
        mock_anthropic.messages.create = AsyncMock(
            return_value=_make_qa_response(qa_payload)
        )
        events, emit = captured_events
        result: QAReview = await agent.execute(
            context={
                "customer_config_v2": ddc_ecommerce,
                "technical_design": design,
                "code_output": code,
            },
            run_id=sample_run_id,
            emit_event=emit,
        )
        assert isinstance(result, QAReview)
        uc_ids = {uc.id for uc in ddc_ecommerce.use_cases}
        coverage_ids = {fc.feature_id for fc in result.requirements_coverage}
        assert coverage_ids == uc_ids, (
            f"Coverage mismatch. Expected use_case ids: {uc_ids}, "
            f"got coverage ids: {coverage_ids}"
        )
        assert len(result.requirements_coverage) == len(ddc_ecommerce.use_cases)

    async def test_revise_code_verdict_when_entity_attribute_missing(
        self, mock_anthropic, ddc_ecommerce: CustomerConfigV2, sample_run_id, captured_events
    ):
        """QA must issue revise_code when a DDC entity attribute is absent from generated code."""
        agent = self._make_agent()
        design = _make_technical_design_from_ddc(ddc_ecommerce)
        code = _make_code_output(ddc_ecommerce)
        qa_payload = _make_revise_code_qa_review(ddc_ecommerce)
        mock_anthropic.messages.create = AsyncMock(
            return_value=_make_qa_response(qa_payload)
        )
        events, emit = captured_events
        result: QAReview = await agent.execute(
            context={
                "customer_config_v2": ddc_ecommerce,
                "technical_design": design,
                "code_output": code,
            },
            run_id=sample_run_id,
            emit_event=emit,
        )
        assert result.verdict == ReviewVerdict.REVISE_CODE
        issue_descriptions = " ".join(i.description for i in result.issues)
        assert "price" in issue_descriptions or "Product" in issue_descriptions

    async def test_approve_verdict_when_all_covered(
        self, mock_anthropic, ddc_ecommerce: CustomerConfigV2, sample_run_id, captured_events
    ):
        agent = self._make_agent()
        design = _make_technical_design_from_ddc(ddc_ecommerce)
        code = _make_code_output(ddc_ecommerce)
        qa_payload = _make_approve_qa_review(ddc_ecommerce)
        mock_anthropic.messages.create = AsyncMock(
            return_value=_make_qa_response(qa_payload)
        )
        events, emit = captured_events
        result: QAReview = await agent.execute(
            context={
                "customer_config_v2": ddc_ecommerce,
                "technical_design": design,
                "code_output": code,
            },
            run_id=sample_run_id,
            emit_event=emit,
        )
        assert result.verdict == ReviewVerdict.APPROVE
        assert result.code_quality_score >= 3

    async def test_reasoning_includes_per_rule_enforcement(
        self, mock_anthropic, ddc_ecommerce: CustomerConfigV2, sample_run_id, captured_events
    ):
        """The reasoning field must contain per-rule enforcement checks."""
        agent = self._make_agent()
        design = _make_technical_design_from_ddc(ddc_ecommerce)
        code = _make_code_output(ddc_ecommerce)
        qa_payload = _make_approve_qa_review(ddc_ecommerce)
        mock_anthropic.messages.create = AsyncMock(
            return_value=_make_qa_response(qa_payload)
        )
        events, emit = captured_events
        result: QAReview = await agent.execute(
            context={
                "customer_config_v2": ddc_ecommerce,
                "technical_design": design,
                "code_output": code,
            },
            run_id=sample_run_id,
            emit_event=emit,
        )
        assert "enforced=" in result.reasoning

    async def test_agent_complete_event_emitted(
        self, mock_anthropic, ddc_ecommerce: CustomerConfigV2, sample_run_id, captured_events
    ):
        agent = self._make_agent()
        design = _make_technical_design_from_ddc(ddc_ecommerce)
        code = _make_code_output(ddc_ecommerce)
        qa_payload = _make_approve_qa_review(ddc_ecommerce)
        mock_anthropic.messages.create = AsyncMock(
            return_value=_make_qa_response(qa_payload)
        )
        events, emit = captured_events
        await agent.execute(
            context={
                "customer_config_v2": ddc_ecommerce,
                "technical_design": design,
                "code_output": code,
            },
            run_id=sample_run_id,
            emit_event=emit,
        )
        types = [e.event_type for e in events]
        assert EventType.AGENT_START in types
        assert EventType.AGENT_COMPLETE in types
