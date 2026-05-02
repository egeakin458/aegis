"""
Base agent class.

All Aegis agents inherit from this class. It handles:
- LLM API calls via the Anthropic SDK
- Output validation against Pydantic schemas
- Event emission for the pipeline runner
- Retry logic on validation failure
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Callable, Type

import anthropic
from anthropic import APIStatusError, APITimeoutError, RateLimitError
from pydantic import BaseModel, ValidationError

from app.config import settings

logger = logging.getLogger(__name__)
from app.schemas.pipeline_events import (
    AgentName,
    EventType,
    PipelineEvent,
    TokenUsage,
)


class BaseAgent:
    """
    Base class for all Aegis pipeline agents.

    Each agent has:
    - A name (AgentName enum)
    - A system prompt template
    - An output schema (Pydantic model) for validation
    - A model identifier (defaults to primary model)

    Subclasses must implement `build_user_prompt(context)` to construct
    the user message from the pipeline context.
    """

    def __init__(
        self,
        name: AgentName,
        system_prompt: str,
        output_schema: Type[BaseModel],
        model: str | None = None,
    ):
        self.name = name
        self.system_prompt = system_prompt
        self.output_schema = output_schema
        self.model = model or settings.primary_model
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    def build_user_prompt(self, context: dict[str, Any]) -> str:
        """
        Build the user message from pipeline context.
        Must be implemented by each agent subclass.
        """
        raise NotImplementedError

    async def execute(
        self,
        context: dict[str, Any],
        run_id: str,
        emit_event: Callable[[PipelineEvent], None],
    ) -> BaseModel:
        """
        Execute the agent: call the LLM, validate output, return parsed result.

        Args:
            context: Pipeline context dict containing upstream agent outputs
            run_id: Current pipeline run ID
            emit_event: Callback to emit pipeline events

        Returns:
            Validated Pydantic model instance

        Raises:
            ValueError: If output fails validation after retry
        """
        user_prompt = self.build_user_prompt(context)

        # Emit start event
        emit_event(PipelineEvent(
            run_id=run_id,
            agent=self.name,
            event_type=EventType.AGENT_START,
            message=self._start_message(),
        ))

        max_attempts = 2
        last_error: ValidationError | json.JSONDecodeError | None = None

        for attempt in range(max_attempts):
            # On retry, append the validation error to help the LLM self-correct
            prompt = user_prompt
            if last_error:
                prompt = (
                    f"{user_prompt}\n\n"
                    f"Your previous response had a formatting error:\n{last_error}\n\n"
                    f"Please respond again with valid JSON matching the required schema exactly."
                )

            result, tokens, duration = await self._call_llm(prompt, run_id, emit_event)

            try:
                parsed = self._validate_output(result)
                emit_event(PipelineEvent(
                    run_id=run_id,
                    agent=self.name,
                    event_type=EventType.AGENT_COMPLETE,
                    message=f"{self._display_name()} completed their work.",
                    tokens_used=tokens,
                    duration_ms=duration,
                ))
                return parsed

            except (ValidationError, json.JSONDecodeError) as e:
                last_error = e
                is_final_attempt = attempt == max_attempts - 1

                if is_final_attempt:
                    emit_event(PipelineEvent(
                        run_id=run_id,
                        agent=self.name,
                        event_type=EventType.ERROR,
                        message=f"{self._display_name()} was unable to produce valid output.",
                        data={"error": str(e)},
                    ))
                    raise ValueError(
                        f"Agent {self.name.value} failed output validation after retry: {e}"
                    ) from e

                emit_event(PipelineEvent(
                    run_id=run_id,
                    agent=self.name,
                    event_type=EventType.VALIDATION_FAILED,
                    message=f"{self._display_name()} is revising their output format...",
                    data={"error": str(e)},
                ))

    async def _call_llm(
        self,
        user_prompt: str,
        run_id: str,
        emit_event: Callable[[PipelineEvent], None],
    ) -> tuple[str, TokenUsage, int]:
        """Make an LLM API call and return (raw_text, token_usage, duration_ms).

        Retries on transient errors (RateLimitError, APITimeoutError, 5xx) with
        exponential backoff. Raises immediately on non-transient errors.
        """
        emit_event(PipelineEvent(
            run_id=run_id,
            agent=self.name,
            event_type=EventType.LLM_CALL_START,
            message=f"{self._display_name()} is thinking...",
        ))

        start = time.time()
        last_exc: Exception | None = None

        for attempt in range(settings.max_llm_retries + 1):
            try:
                response = await self.client.messages.create(
                    model=self.model,
                    max_tokens=settings.max_tokens,
                    timeout=settings.api_timeout,
                    system=[{
                        "type": "text",
                        "text": self.system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }],
                    messages=[{"role": "user", "content": user_prompt}],
                )

                duration_ms = int((time.time() - start) * 1000)
                raw_text = response.content[0].text
                tokens = TokenUsage(
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                )

                emit_event(PipelineEvent(
                    run_id=run_id,
                    agent=self.name,
                    event_type=EventType.LLM_CALL_COMPLETE,
                    message=f"{self._display_name()} has a response ready.",
                    tokens_used=tokens,
                    duration_ms=duration_ms,
                ))

                return raw_text, tokens, duration_ms

            except (RateLimitError, APITimeoutError) as exc:
                last_exc = exc
            except APIStatusError as exc:
                if 500 <= exc.status_code < 600:
                    last_exc = exc
                else:
                    raise

            if attempt < settings.max_llm_retries:
                delay = settings.llm_retry_base_delay_seconds * (2 ** attempt)
                logger.warning(
                    "LLM call failed (attempt %d/%d): %s. Retrying in %.1fs.",
                    attempt + 1, settings.max_llm_retries + 1, last_exc, delay,
                )
                await asyncio.sleep(delay)

        raise last_exc

    def _validate_output(self, raw_text: str) -> BaseModel:
        """Parse and validate agent output against the schema."""
        # Strip markdown code fences if present
        text = raw_text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        data = json.loads(text)
        return self.output_schema.model_validate(data)

    def _display_name(self) -> str:
        """Human-friendly agent name for UI messages."""
        names = {
            AgentName.REQUIREMENTS_ANALYST: "Your project analyst",
            AgentName.SOLUTION_ARCHITECT: "Our architect",
            AgentName.DEVELOPER: "Our developer",
            AgentName.QA_REVIEWER: "Our quality reviewer",
            AgentName.SYSTEM: "Aegis",
        }
        return names.get(self.name, self.name.value)

    def _start_message(self) -> str:
        """Human-friendly start message for the UI."""
        messages = {
            AgentName.REQUIREMENTS_ANALYST: "Your project analyst is reviewing your requirements...",
            AgentName.SOLUTION_ARCHITECT: "Our architect is designing the structure of your application...",
            AgentName.DEVELOPER: "Our developer is building your application...",
            AgentName.QA_REVIEWER: "Quality review in progress...",
        }
        return messages.get(self.name, f"{self.name.value} is starting...")
