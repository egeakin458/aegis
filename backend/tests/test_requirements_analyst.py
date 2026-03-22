"""
Tests for the Requirements Analyst agent and the RAOutput schema.

Coverage:
  1. RAOutput schema validation (happy path, constraint violations, edge cases)
  2. RequirementsAnalyst.build_user_prompt() — all three prompt branches
  3. RequirementsAnalyst.execute() with mocked LLM — clarification path,
     finalization path, validation retry path, and double-failure path
  4. Event emission — type, order, and field correctness
"""

from __future__ import annotations

import json
from typing import Callable
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from app.agents.requirements_analyst import RequirementsAnalyst
from app.schemas.customer_config import (
    AssumedField,
    BusinessContext,
    BusinessSize,
    ClarificationQuestion,
    ClarificationRound,
    CustomerConfig,
    DataRequirements,
    FeatureRequest,
    Features,
    FinalizedConfig,
    IndustryType,
    ProblemStatement,
    UserType,
)
from app.schemas.pipeline_events import EventType, PipelineEvent, TokenUsage
from app.schemas.ra_output import RAOutput


# ===========================================================================
# Helpers
# ===========================================================================

def _clarification_payload(
    questions: list[dict] | None = None,
    reasoning: str = "Some things need clarification.",
) -> dict:
    """Build a minimal needs_clarification=True RAOutput payload."""
    if questions is None:
        questions = [
            {
                "id": "q1",
                "topic": "authentication",
                "original_input": "Need an online ordering system",
                "question": "Should customers need to log in?",
                "suggestions": ["Yes", "No", "Optional"],
            }
        ]
    return {
        "needs_clarification": True,
        "reasoning": reasoning,
        "questions": questions,
    }


def _finalization_payload(
    customer_config: CustomerConfig,
    reasoning: str = "All clear.",
) -> dict:
    """Build a minimal needs_clarification=False RAOutput payload."""
    return {
        "needs_clarification": False,
        "reasoning": reasoning,
        "finalized_config": {
            "config": customer_config.model_dump(mode="json"),
            "assumptions": [],
            "clarification_history": [],
            "project_summary": "An online ordering system for a coffee shop.",
            "is_complete": True,
        },
    }


def _make_response(payload: dict) -> MagicMock:
    content_block = MagicMock()
    content_block.text = json.dumps(payload)
    usage = MagicMock()
    usage.input_tokens = 150
    usage.output_tokens = 300
    response = MagicMock()
    response.content = [content_block]
    response.usage = usage
    return response


# ===========================================================================
# 1. RAOutput schema validation
# ===========================================================================

class TestRAOutputSchema:
    """Validates the RAOutput Pydantic model and its model_validator."""

    # --- Happy path ---

    def test_clarification_output_with_one_question(
        self, sample_clarification_question: ClarificationQuestion
    ):
        output = RAOutput(
            needs_clarification=True,
            reasoning="The feature scope is unclear.",
            questions=[sample_clarification_question],
        )
        assert output.needs_clarification is True
        assert len(output.questions) == 1
        assert output.questions[0].id == "q1"

    def test_clarification_output_with_ten_questions(self):
        questions = [
            ClarificationQuestion(
                id=f"q{i}",
                topic="topic",
                original_input="some input",
                question=f"Question {i}?",
                suggestions=["A", "B"],
            )
            for i in range(1, 11)
        ]
        output = RAOutput(
            needs_clarification=True,
            reasoning="Many ambiguities.",
            questions=questions,
        )
        assert len(output.questions) == 10

    def test_finalization_output_without_questions(
        self, valid_finalized_config: FinalizedConfig
    ):
        output = RAOutput(
            needs_clarification=False,
            reasoning="Configuration is complete.",
            finalized_config=valid_finalized_config,
        )
        assert output.needs_clarification is False
        assert output.finalized_config is not None
        assert output.questions is None

    def test_finalization_output_questions_field_is_optional_none(
        self, valid_finalized_config: FinalizedConfig
    ):
        """questions may be explicitly None when needs_clarification is False."""
        output = RAOutput(
            needs_clarification=False,
            reasoning="Complete.",
            questions=None,
            finalized_config=valid_finalized_config,
        )
        assert output.questions is None

    def test_reasoning_field_is_required(self, valid_finalized_config: FinalizedConfig):
        with pytest.raises(ValidationError):
            RAOutput(
                needs_clarification=False,
                finalized_config=valid_finalized_config,
            )

    # --- Constraint violations ---

    def test_clarification_true_requires_at_least_one_question(self):
        with pytest.raises(ValidationError, match="questions must be provided"):
            RAOutput(
                needs_clarification=True,
                reasoning="Some gaps found.",
                questions=None,
            )

    def test_clarification_true_rejects_empty_questions_list(self):
        with pytest.raises(ValidationError, match="questions must be provided"):
            RAOutput(
                needs_clarification=True,
                reasoning="Some gaps found.",
                questions=[],
            )

    def test_clarification_true_rejects_eleven_questions(self):
        questions = [
            ClarificationQuestion(
                id=f"q{i}",
                topic="topic",
                original_input="input",
                question=f"Question {i}?",
                suggestions=["A", "B"],
            )
            for i in range(1, 12)  # 11 questions
        ]
        with pytest.raises(ValidationError, match="Maximum 10 questions"):
            RAOutput(
                needs_clarification=True,
                reasoning="Lots of gaps.",
                questions=questions,
            )

    def test_finalization_false_requires_finalized_config(self):
        with pytest.raises(ValidationError, match="finalized_config must be provided"):
            RAOutput(
                needs_clarification=False,
                reasoning="All good.",
                finalized_config=None,
            )

    def test_needs_clarification_field_is_required(self):
        with pytest.raises(ValidationError):
            RAOutput(reasoning="test")

    # --- Edge cases ---

    def test_clarification_output_question_without_suggestions(self):
        """suggestions has a default_factory=list, so it can be empty."""
        question = ClarificationQuestion(
            id="q1",
            topic="scope",
            original_input="manage data",
            question="What data needs managing?",
        )
        output = RAOutput(
            needs_clarification=True,
            reasoning="Vague feature description.",
            questions=[question],
        )
        assert output.questions[0].suggestions == []

    def test_finalization_output_with_full_clarification_history(
        self,
        valid_customer_config: CustomerConfig,
        sample_clarification_round: ClarificationRound,
    ):
        finalized = FinalizedConfig(
            config=valid_customer_config,
            clarification_history=[sample_clarification_round],
            project_summary="An online ordering system.",
            is_complete=True,
        )
        output = RAOutput(
            needs_clarification=False,
            reasoning="Resolved after one round.",
            finalized_config=finalized,
        )
        assert len(output.finalized_config.clarification_history) == 1

    def test_reasoning_with_unicode_characters(
        self, sample_clarification_question: ClarificationQuestion
    ):
        output = RAOutput(
            needs_clarification=True,
            reasoning="Ambiguity detected: café menu has 3 items — espresso, latte & cappuccino.",
            questions=[sample_clarification_question],
        )
        assert "café" in output.reasoning


# ===========================================================================
# 2. RequirementsAnalyst.build_user_prompt()
# ===========================================================================

class TestBuildUserPrompt:
    """Tests for the three prompt construction branches."""

    @pytest.fixture(autouse=True)
    def _agent(self, mock_anthropic):
        """Instantiate the agent with the Anthropic client already mocked."""
        self.agent = RequirementsAnalyst()

    # --- Mode "analyze" without history (initial round) ---

    def test_analyze_mode_no_history_contains_mode_a(
        self, valid_customer_config: CustomerConfig
    ):
        prompt = self.agent.build_user_prompt({"customer_config": valid_customer_config})
        assert "MODE A" in prompt

    def test_analyze_mode_no_history_contains_config_json(
        self, valid_customer_config: CustomerConfig
    ):
        prompt = self.agent.build_user_prompt({"customer_config": valid_customer_config})
        assert "Cafe Latte" in prompt

    def test_analyze_mode_no_history_mentions_initial_round(
        self, valid_customer_config: CustomerConfig
    ):
        prompt = self.agent.build_user_prompt({"customer_config": valid_customer_config})
        assert "round 1" in prompt.lower() or "initial analysis" in prompt.lower()

    def test_analyze_mode_no_history_does_not_contain_clarification_history_section(
        self, valid_customer_config: CustomerConfig
    ):
        """Without history there should be no CLARIFICATION HISTORY block."""
        prompt = self.agent.build_user_prompt({"customer_config": valid_customer_config})
        assert "CLARIFICATION HISTORY" not in prompt

    def test_default_mode_is_analyze(self, valid_customer_config: CustomerConfig):
        """When mode key is absent from context, it defaults to analyze."""
        context_without_mode = {"customer_config": valid_customer_config}
        prompt = self.agent.build_user_prompt(context_without_mode)
        assert "MODE A" in prompt

    # --- Mode "analyze" with clarification history ---

    def test_analyze_mode_with_history_contains_mode_a(
        self,
        valid_customer_config: CustomerConfig,
        sample_clarification_round: ClarificationRound,
    ):
        prompt = self.agent.build_user_prompt(
            {
                "customer_config": valid_customer_config,
                "mode": "analyze",
                "clarification_history": [sample_clarification_round],
            }
        )
        assert "MODE A" in prompt

    def test_analyze_mode_with_history_shows_round_number(
        self,
        valid_customer_config: CustomerConfig,
        sample_clarification_round: ClarificationRound,
    ):
        """With one existing round, the prompt should indicate we are in round 2."""
        prompt = self.agent.build_user_prompt(
            {
                "customer_config": valid_customer_config,
                "mode": "analyze",
                "clarification_history": [sample_clarification_round],
            }
        )
        assert "round 2" in prompt.lower()

    def test_analyze_mode_with_history_contains_history_json(
        self,
        valid_customer_config: CustomerConfig,
        sample_clarification_round: ClarificationRound,
    ):
        prompt = self.agent.build_user_prompt(
            {
                "customer_config": valid_customer_config,
                "mode": "analyze",
                "clarification_history": [sample_clarification_round],
            }
        )
        # The question id should appear in the serialised history JSON
        assert "q1" in prompt

    def test_analyze_mode_with_history_includes_config_json(
        self,
        valid_customer_config: CustomerConfig,
        sample_clarification_round: ClarificationRound,
    ):
        prompt = self.agent.build_user_prompt(
            {
                "customer_config": valid_customer_config,
                "mode": "analyze",
                "clarification_history": [sample_clarification_round],
            }
        )
        assert "Cafe Latte" in prompt

    def test_analyze_mode_with_two_history_rounds_shows_round_three(
        self,
        valid_customer_config: CustomerConfig,
        sample_clarification_round: ClarificationRound,
    ):
        second_round = ClarificationRound(
            round_number=2,
            questions=[
                ClarificationQuestion(
                    id="q2",
                    topic="data",
                    original_input="manage data",
                    question="What data needs managing?",
                    suggestions=["Ingredients", "Products", "Orders"],
                )
            ],
            answers={"q2": "Products"},
        )
        prompt = self.agent.build_user_prompt(
            {
                "customer_config": valid_customer_config,
                "mode": "analyze",
                "clarification_history": [sample_clarification_round, second_round],
            }
        )
        assert "round 3" in prompt.lower()

    # --- Mode "finalize" ---

    def test_finalize_mode_contains_mode_b(
        self, valid_customer_config: CustomerConfig
    ):
        prompt = self.agent.build_user_prompt(
            {"customer_config": valid_customer_config, "mode": "finalize"}
        )
        assert "MODE B" in prompt

    def test_finalize_mode_contains_config_json(
        self, valid_customer_config: CustomerConfig
    ):
        prompt = self.agent.build_user_prompt(
            {"customer_config": valid_customer_config, "mode": "finalize"}
        )
        assert "Cafe Latte" in prompt

    def test_finalize_mode_with_no_history_still_produces_valid_prompt(
        self, valid_customer_config: CustomerConfig
    ):
        prompt = self.agent.build_user_prompt(
            {"customer_config": valid_customer_config, "mode": "finalize"}
        )
        assert "CLARIFICATION HISTORY" in prompt
        assert len(prompt) > 50

    def test_finalize_mode_with_history_includes_history_json(
        self,
        valid_customer_config: CustomerConfig,
        sample_clarification_round: ClarificationRound,
    ):
        prompt = self.agent.build_user_prompt(
            {
                "customer_config": valid_customer_config,
                "mode": "finalize",
                "clarification_history": [sample_clarification_round],
            }
        )
        assert "q1" in prompt

    def test_finalize_mode_instructs_agent_to_set_needs_clarification_false(
        self, valid_customer_config: CustomerConfig
    ):
        prompt = self.agent.build_user_prompt(
            {"customer_config": valid_customer_config, "mode": "finalize"}
        )
        assert "needs_clarification" in prompt
        assert "false" in prompt.lower()


# ===========================================================================
# 3. RequirementsAnalyst.execute() with mocked LLM
# ===========================================================================

class TestExecute:
    """End-to-end execute() tests with no real API calls."""

    @pytest.fixture(autouse=True)
    def _agent(self, mock_anthropic):
        self.agent = RequirementsAnalyst()
        self.mock_client = mock_anthropic

    # --- Clarification path ---

    @pytest.mark.asyncio
    async def test_execute_returns_raoutput_when_clarification_needed(
        self,
        valid_customer_config: CustomerConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        payload = _clarification_payload()
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(payload)
        )

        result = await self.agent.execute(
            context={"customer_config": valid_customer_config, "mode": "analyze"},
            run_id=sample_run_id,
            emit_event=emit,
        )

        assert isinstance(result, RAOutput)
        assert result.needs_clarification is True
        assert len(result.questions) == 1
        assert result.questions[0].id == "q1"

    @pytest.mark.asyncio
    async def test_execute_clarification_result_has_correct_question_fields(
        self,
        valid_customer_config: CustomerConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        payload = _clarification_payload(
            questions=[
                {
                    "id": "feature-scope",
                    "topic": "Features",
                    "original_input": "manage data",
                    "question": "What type of data do you need to manage?",
                    "suggestions": ["Ingredients", "Finished products", "Both"],
                }
            ]
        )
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(payload)
        )

        result = await self.agent.execute(
            context={"customer_config": valid_customer_config},
            run_id=sample_run_id,
            emit_event=emit,
        )

        assert result.questions[0].id == "feature-scope"
        assert result.questions[0].topic == "Features"
        assert len(result.questions[0].suggestions) == 3

    # --- Finalization path ---

    @pytest.mark.asyncio
    async def test_execute_returns_raoutput_when_finalized(
        self,
        valid_customer_config: CustomerConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        payload = _finalization_payload(valid_customer_config)
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(payload)
        )

        result = await self.agent.execute(
            context={"customer_config": valid_customer_config, "mode": "finalize"},
            run_id=sample_run_id,
            emit_event=emit,
        )

        assert isinstance(result, RAOutput)
        assert result.needs_clarification is False
        assert result.finalized_config is not None
        assert result.finalized_config.is_complete is True

    @pytest.mark.asyncio
    async def test_execute_finalization_preserves_project_summary(
        self,
        valid_customer_config: CustomerConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        expected_summary = "A pickup ordering system for Cafe Latte patrons."
        payload = _finalization_payload(valid_customer_config)
        payload["finalized_config"]["project_summary"] = expected_summary
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(payload)
        )

        result = await self.agent.execute(
            context={"customer_config": valid_customer_config, "mode": "finalize"},
            run_id=sample_run_id,
            emit_event=emit,
        )

        assert result.finalized_config.project_summary == expected_summary

    # --- Markdown fence stripping ---

    @pytest.mark.asyncio
    async def test_execute_handles_markdown_json_fences(
        self,
        valid_customer_config: CustomerConfig,
        sample_run_id: str,
        captured_events,
    ):
        """The base class strips ```json ... ``` fences before parsing."""
        events, emit = captured_events
        raw_json = json.dumps(_clarification_payload())
        wrapped_in_fences = f"```json\n{raw_json}\n```"

        content_block = MagicMock()
        content_block.text = wrapped_in_fences
        usage = MagicMock()
        usage.input_tokens = 50
        usage.output_tokens = 100
        fenced_response = MagicMock()
        fenced_response.content = [content_block]
        fenced_response.usage = usage

        self.mock_client.messages.create = AsyncMock(return_value=fenced_response)

        result = await self.agent.execute(
            context={"customer_config": valid_customer_config},
            run_id=sample_run_id,
            emit_event=emit,
        )

        assert isinstance(result, RAOutput)
        assert result.needs_clarification is True

    # --- Validation retry path ---

    @pytest.mark.asyncio
    async def test_execute_retries_on_first_schema_validation_failure(
        self,
        valid_customer_config: CustomerConfig,
        sample_run_id: str,
        captured_events,
    ):
        """
        First call returns valid JSON but invalid RAOutput schema
        (needs_clarification=True with empty questions) → retry → valid → returns result.

        Note: bare JSON decode errors (non-JSON text) propagate uncaught from
        _validate_output because the execute() loop only catches ValidationError.
        Only Pydantic ValidationError triggers the retry path.
        """
        events, emit = captured_events

        # Valid JSON, but fails RAOutput.model_validator (questions empty)
        invalid_schema_payload = {
            "needs_clarification": True,
            "reasoning": "Gaps found.",
            "questions": [],
        }
        invalid_response = _make_response(invalid_schema_payload)
        valid_response = _make_response(_clarification_payload())

        self.mock_client.messages.create = AsyncMock(
            side_effect=[invalid_response, valid_response]
        )

        result = await self.agent.execute(
            context={"customer_config": valid_customer_config},
            run_id=sample_run_id,
            emit_event=emit,
        )

        assert isinstance(result, RAOutput)
        assert result.needs_clarification is True
        assert self.mock_client.messages.create.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_retry_prompt_includes_original_error(
        self,
        valid_customer_config: CustomerConfig,
        sample_run_id: str,
        captured_events,
    ):
        """The second LLM call's prompt must include the validation error text."""
        events, emit = captured_events
        captured_prompts = []

        async def capture_and_respond(*args, **kwargs):
            captured_prompts.append(kwargs.get("messages", []))
            call_number = len(captured_prompts)
            if call_number == 1:
                return _make_response(
                    {"needs_clarification": True, "reasoning": "x", "questions": []}
                )
            return _make_response(_clarification_payload())

        self.mock_client.messages.create = capture_and_respond

        await self.agent.execute(
            context={"customer_config": valid_customer_config},
            run_id=sample_run_id,
            emit_event=emit,
        )

        # The second call's user message content should mention the formatting error
        second_call_messages = captured_prompts[1]
        user_content = second_call_messages[0]["content"]
        assert "formatting error" in user_content.lower() or "error" in user_content.lower()

    # --- Double failure path ---

    @pytest.mark.asyncio
    async def test_execute_raises_value_error_after_two_schema_invalid_responses(
        self,
        valid_customer_config: CustomerConfig,
        sample_run_id: str,
        captured_events,
    ):
        """
        Both attempts return valid JSON but invalid RAOutput schema → ValueError.

        The retry path is triggered by Pydantic ValidationError only.
        Both calls returning the same schema-invalid payload means both attempts fail,
        and after the second failure execute() raises ValueError.
        """
        events, emit = captured_events

        invalid_payload = {
            "needs_clarification": True,
            "reasoning": "Gaps found.",
            "questions": [],  # fails model_validator
        }

        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(invalid_payload)
        )

        with pytest.raises(ValueError, match="failed output validation after retry"):
            await self.agent.execute(
                context={"customer_config": valid_customer_config},
                run_id=sample_run_id,
                emit_event=emit,
            )

        assert self.mock_client.messages.create.call_count == 2

    # --- Token and timing tracking ---

    @pytest.mark.asyncio
    async def test_execute_agent_complete_event_carries_token_usage(
        self,
        valid_customer_config: CustomerConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events

        response = _make_response(_clarification_payload())
        response.usage.input_tokens = 500
        response.usage.output_tokens = 250

        self.mock_client.messages.create = AsyncMock(return_value=response)

        await self.agent.execute(
            context={"customer_config": valid_customer_config},
            run_id=sample_run_id,
            emit_event=emit,
        )

        complete_event = next(
            e for e in events if e.event_type == EventType.AGENT_COMPLETE
        )
        assert complete_event.tokens_used is not None
        assert complete_event.tokens_used.input_tokens == 500
        assert complete_event.tokens_used.output_tokens == 250

    @pytest.mark.asyncio
    async def test_execute_agent_complete_event_has_duration_ms(
        self,
        valid_customer_config: CustomerConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(_clarification_payload())
        )

        await self.agent.execute(
            context={"customer_config": valid_customer_config},
            run_id=sample_run_id,
            emit_event=emit,
        )

        complete_event = next(
            e for e in events if e.event_type == EventType.AGENT_COMPLETE
        )
        assert complete_event.duration_ms is not None
        assert complete_event.duration_ms >= 0


# ===========================================================================
# 4. Event emission
# ===========================================================================

class TestEventEmission:
    """Verifies that the correct events are emitted in the correct order."""

    @pytest.fixture(autouse=True)
    def _agent(self, mock_anthropic):
        self.agent = RequirementsAnalyst()
        self.mock_client = mock_anthropic

    def _event_types(self, events: list[PipelineEvent]) -> list[EventType]:
        return [e.event_type for e in events]

    # --- Successful run ---

    @pytest.mark.asyncio
    async def test_successful_run_emits_start_before_llm_call(
        self,
        valid_customer_config: CustomerConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(_clarification_payload())
        )

        await self.agent.execute(
            context={"customer_config": valid_customer_config},
            run_id=sample_run_id,
            emit_event=emit,
        )

        types = self._event_types(events)
        assert types.index(EventType.AGENT_START) < types.index(EventType.LLM_CALL_START)

    @pytest.mark.asyncio
    async def test_successful_run_event_sequence(
        self,
        valid_customer_config: CustomerConfig,
        sample_run_id: str,
        captured_events,
    ):
        """Expected order: AGENT_START → LLM_CALL_START → LLM_CALL_COMPLETE → AGENT_COMPLETE."""
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(_clarification_payload())
        )

        await self.agent.execute(
            context={"customer_config": valid_customer_config},
            run_id=sample_run_id,
            emit_event=emit,
        )

        types = self._event_types(events)
        assert EventType.AGENT_START in types
        assert EventType.LLM_CALL_START in types
        assert EventType.LLM_CALL_COMPLETE in types
        assert EventType.AGENT_COMPLETE in types

        assert types.index(EventType.AGENT_START) < types.index(EventType.LLM_CALL_START)
        assert types.index(EventType.LLM_CALL_START) < types.index(EventType.LLM_CALL_COMPLETE)
        assert types.index(EventType.LLM_CALL_COMPLETE) < types.index(EventType.AGENT_COMPLETE)

    @pytest.mark.asyncio
    async def test_agent_start_event_has_correct_run_id(
        self,
        valid_customer_config: CustomerConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(_clarification_payload())
        )

        await self.agent.execute(
            context={"customer_config": valid_customer_config},
            run_id=sample_run_id,
            emit_event=emit,
        )

        start_event = next(e for e in events if e.event_type == EventType.AGENT_START)
        assert start_event.run_id == sample_run_id

    @pytest.mark.asyncio
    async def test_agent_start_event_has_requirements_analyst_agent_name(
        self,
        valid_customer_config: CustomerConfig,
        sample_run_id: str,
        captured_events,
    ):
        from app.schemas.pipeline_events import AgentName

        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(_clarification_payload())
        )

        await self.agent.execute(
            context={"customer_config": valid_customer_config},
            run_id=sample_run_id,
            emit_event=emit,
        )

        start_event = next(e for e in events if e.event_type == EventType.AGENT_START)
        assert start_event.agent == AgentName.REQUIREMENTS_ANALYST

    @pytest.mark.asyncio
    async def test_llm_call_complete_event_carries_token_counts(
        self,
        valid_customer_config: CustomerConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        response = _make_response(_clarification_payload())
        response.usage.input_tokens = 400
        response.usage.output_tokens = 100
        self.mock_client.messages.create = AsyncMock(return_value=response)

        await self.agent.execute(
            context={"customer_config": valid_customer_config},
            run_id=sample_run_id,
            emit_event=emit,
        )

        llm_complete = next(
            e for e in events if e.event_type == EventType.LLM_CALL_COMPLETE
        )
        assert llm_complete.tokens_used.input_tokens == 400
        assert llm_complete.tokens_used.output_tokens == 100

    # --- Retry run ---

    @pytest.mark.asyncio
    async def test_retry_run_emits_validation_failed_before_second_llm_call(
        self,
        valid_customer_config: CustomerConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            side_effect=[
                _make_response(
                    {"needs_clarification": True, "reasoning": "x", "questions": []}
                ),
                _make_response(_clarification_payload()),
            ]
        )

        await self.agent.execute(
            context={"customer_config": valid_customer_config},
            run_id=sample_run_id,
            emit_event=emit,
        )

        types = self._event_types(events)
        assert EventType.VALIDATION_FAILED in types

        # VALIDATION_FAILED must come after the first LLM_CALL_COMPLETE
        # and before the second LLM_CALL_START
        first_llm_complete = next(
            i for i, t in enumerate(types) if t == EventType.LLM_CALL_COMPLETE
        )
        validation_failed_idx = types.index(EventType.VALIDATION_FAILED)
        assert validation_failed_idx > first_llm_complete

    @pytest.mark.asyncio
    async def test_retry_run_ultimately_emits_agent_complete(
        self,
        valid_customer_config: CustomerConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            side_effect=[
                _make_response(
                    {"needs_clarification": True, "reasoning": "x", "questions": []}
                ),
                _make_response(_clarification_payload()),
            ]
        )

        await self.agent.execute(
            context={"customer_config": valid_customer_config},
            run_id=sample_run_id,
            emit_event=emit,
        )

        types = self._event_types(events)
        assert EventType.AGENT_COMPLETE in types
        assert EventType.ERROR not in types

    # --- Failure run ---

    @pytest.mark.asyncio
    async def test_double_failure_emits_error_event(
        self,
        valid_customer_config: CustomerConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(
                {"needs_clarification": True, "reasoning": "x", "questions": []}
            )
        )

        with pytest.raises(ValueError):
            await self.agent.execute(
                context={"customer_config": valid_customer_config},
                run_id=sample_run_id,
                emit_event=emit,
            )

        types = self._event_types(events)
        assert EventType.ERROR in types

    @pytest.mark.asyncio
    async def test_double_failure_error_event_is_last(
        self,
        valid_customer_config: CustomerConfig,
        sample_run_id: str,
        captured_events,
    ):
        """After double failure the ERROR event must be the final emitted event."""
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(
                {"needs_clarification": True, "reasoning": "x", "questions": []}
            )
        )

        with pytest.raises(ValueError):
            await self.agent.execute(
                context={"customer_config": valid_customer_config},
                run_id=sample_run_id,
                emit_event=emit,
            )

        assert events[-1].event_type == EventType.ERROR

    @pytest.mark.asyncio
    async def test_double_failure_error_event_contains_error_data(
        self,
        valid_customer_config: CustomerConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(
                {"needs_clarification": True, "reasoning": "x", "questions": []}
            )
        )

        with pytest.raises(ValueError):
            await self.agent.execute(
                context={"customer_config": valid_customer_config},
                run_id=sample_run_id,
                emit_event=emit,
            )

        error_event = next(e for e in events if e.event_type == EventType.ERROR)
        assert "error" in error_event.data
        assert "raw_output" not in error_event.data

    @pytest.mark.asyncio
    async def test_double_failure_no_agent_complete_event(
        self,
        valid_customer_config: CustomerConfig,
        sample_run_id: str,
        captured_events,
    ):
        events, emit = captured_events
        self.mock_client.messages.create = AsyncMock(
            return_value=_make_response(
                {"needs_clarification": True, "reasoning": "x", "questions": []}
            )
        )

        with pytest.raises(ValueError):
            await self.agent.execute(
                context={"customer_config": valid_customer_config},
                run_id=sample_run_id,
                emit_event=emit,
            )

        types = self._event_types(events)
        assert EventType.AGENT_COMPLETE not in types
