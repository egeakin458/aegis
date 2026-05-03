"""
Tests for the Requirements Analyst agent in DDC mode and the
RAOutputDDC schema.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from app.agents.requirements_analyst import RequirementsAnalyst
from app.schemas.customer_config import (
    ClarificationQuestion,
    CustomerConfigV2,
)
from app.schemas.pipeline_events import EventType
from app.schemas.ra_output import RAOutputDDC


# ===========================================================================
# Helpers
# ===========================================================================


def _ddc_clarification_payload() -> dict:
    return {
        "needs_clarification": True,
        "reasoning": "The domain description is too vague to infer entity attributes.",
        "questions": [
            {
                "id": "q1",
                "topic": "entities",
                "original_input": "manage products",
                "question": "What information do you need to store for each product?",
                "suggestions": ["Name and price only", "Name, price, and stock", "Name, price, stock, and images"],
            }
        ],
    }


def _ddc_finalized_payload(ddc: dict) -> dict:
    return {
        "needs_clarification": False,
        "reasoning": "The input is clear. Producing full DDC.",
        "finalized_config": ddc,
    }


def _make_ddc_response(payload: dict) -> MagicMock:
    content_block = MagicMock()
    content_block.text = json.dumps(payload)
    usage = MagicMock()
    usage.input_tokens = 200
    usage.output_tokens = 500
    response = MagicMock()
    response.content = [content_block]
    response.usage = usage
    return response


# ===========================================================================
# DDC schema and prompt
# ===========================================================================


class TestDDCSchema:
    """Sync tests for RAOutputDDC schema and RA prompt in DDC mode."""

    def _make_agent(self) -> RequirementsAnalyst:
        return RequirementsAnalyst()

    def test_ra_output_ddc_clarification_valid(self):
        output = RAOutputDDC(
            needs_clarification=True,
            reasoning="Missing actor details.",
            questions=[
                ClarificationQuestion(
                    id="q1",
                    topic="actors",
                    original_input="users",
                    question="Who are the main users of this application?",
                    suggestions=["Customers only", "Customers and admins", "Employees only"],
                )
            ],
        )
        assert output.needs_clarification is True
        assert len(output.questions) == 1

    def test_ra_output_ddc_max_5_questions_enforced(self):
        questions = [
            ClarificationQuestion(
                id=f"q{i}", topic="t", original_input="x",
                question=f"Q{i}?", suggestions=["A", "B"],
            )
            for i in range(1, 7)  # 6 questions — should fail
        ]
        with pytest.raises(ValidationError, match="Maximum 5 questions"):
            RAOutputDDC(
                needs_clarification=True,
                reasoning="Too many questions test.",
                questions=questions,
            )

    def test_ra_output_ddc_finalized_requires_config(self):
        with pytest.raises(ValidationError, match="finalized_config must be provided"):
            RAOutputDDC(needs_clarification=False, reasoning="Done.")

    def test_ddc_prompt_contains_schema(self, mock_anthropic):
        agent = self._make_agent()
        assert "CustomerConfigV2" in agent.system_prompt or "ddc-v1" in agent.system_prompt

    def test_ddc_prompt_contains_id_instruction(self, mock_anthropic):
        agent = self._make_agent()
        assert "id" in agent.system_prompt.lower()

    def test_ddc_user_prompt_free_text(self, mock_anthropic):
        agent = self._make_agent()
        prompt = agent.build_user_prompt({"free_text_intent": "A booking system for a yoga studio."})
        assert "yoga studio" in prompt
        assert "FREE-TEXT" in prompt

    def test_ddc_user_prompt_does_not_contain_legacy_mode_label(self, mock_anthropic):
        agent = self._make_agent()
        prompt = agent.build_user_prompt({"free_text_intent": "online shop"})
        assert "MODE A" not in prompt
        assert "DDC" in prompt or "CustomerConfigV2" in prompt or "TASK" in prompt


# ===========================================================================
# DDC execute
# ===========================================================================


@pytest.mark.asyncio
class TestDDC:
    """Async tests for RequirementsAnalyst.execute() in DDC mode."""

    def _make_agent(self) -> RequirementsAnalyst:
        return RequirementsAnalyst()

    async def test_ddc_returns_valid_ddc_on_success(
        self, mock_anthropic, ddc_ecommerce: CustomerConfigV2, sample_run_id, captured_events
    ):
        agent = self._make_agent()
        ddc_dict = ddc_ecommerce.model_dump(mode="json")
        mock_anthropic.messages.create = AsyncMock(
            return_value=_make_ddc_response(_ddc_finalized_payload(ddc_dict))
        )
        events, emit = captured_events
        result = await agent.execute(
            context={"customer_config_v2": ddc_ecommerce},
            run_id=sample_run_id,
            emit_event=emit,
        )
        assert isinstance(result, RAOutputDDC)
        assert result.needs_clarification is False
        assert isinstance(result.finalized_config, CustomerConfigV2)
        assert len(result.finalized_config.actors) == 2

    async def test_ddc_returns_clarification_when_needed(
        self, mock_anthropic, sample_run_id, captured_events
    ):
        agent = self._make_agent()
        mock_anthropic.messages.create = AsyncMock(
            return_value=_make_ddc_response(_ddc_clarification_payload())
        )
        events, emit = captured_events
        result = await agent.execute(
            context={"free_text_intent": "A vague idea about something."},
            run_id=sample_run_id,
            emit_event=emit,
        )
        assert isinstance(result, RAOutputDDC)
        assert result.needs_clarification is True
        assert result.questions is not None
        assert len(result.questions) == 1

    async def test_ddc_recovers_on_retry_after_invalid_output(
        self, mock_anthropic, ddc_ecommerce: CustomerConfigV2, sample_run_id, captured_events
    ):
        """LLM returns garbage first, then valid DDC — must succeed."""
        agent = self._make_agent()
        ddc_dict = ddc_ecommerce.model_dump(mode="json")
        bad_response = MagicMock()
        bad_response.content = [MagicMock(text="not valid json!!!")]
        bad_response.usage = MagicMock(input_tokens=10, output_tokens=5)

        good_response = _make_ddc_response(_ddc_finalized_payload(ddc_dict))

        mock_anthropic.messages.create = AsyncMock(
            side_effect=[bad_response, good_response]
        )
        events, emit = captured_events
        result = await agent.execute(
            context={"customer_config_v2": ddc_ecommerce},
            run_id=sample_run_id,
            emit_event=emit,
        )
        assert isinstance(result, RAOutputDDC)
        assert result.needs_clarification is False
        types = [e.event_type for e in events]
        assert EventType.VALIDATION_FAILED in types
        assert EventType.AGENT_COMPLETE in types

    async def test_ddc_raises_after_double_failure(
        self, mock_anthropic, sample_run_id, captured_events
    ):
        agent = self._make_agent()
        bad = MagicMock()
        bad.content = [MagicMock(text="{{invalid}}")]
        bad.usage = MagicMock(input_tokens=10, output_tokens=5)
        mock_anthropic.messages.create = AsyncMock(return_value=bad)
        events, emit = captured_events
        with pytest.raises(ValueError):
            await agent.execute(
                context={"free_text_intent": "something"},
                run_id=sample_run_id,
                emit_event=emit,
            )
        types = [e.event_type for e in events]
        assert EventType.AGENT_COMPLETE not in types
        assert EventType.ERROR in types

    async def test_ddc_agent_complete_event_emitted(
        self, mock_anthropic, ddc_ecommerce: CustomerConfigV2, sample_run_id, captured_events
    ):
        agent = self._make_agent()
        ddc_dict = ddc_ecommerce.model_dump(mode="json")
        mock_anthropic.messages.create = AsyncMock(
            return_value=_make_ddc_response(_ddc_finalized_payload(ddc_dict))
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
