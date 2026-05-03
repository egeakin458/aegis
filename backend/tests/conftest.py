"""
Shared pytest fixtures for the Aegis backend test suite.
"""

from __future__ import annotations

import json
from typing import Callable
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.customer_config import CustomerConfigV2
from app.schemas.pipeline_events import PipelineEvent, TokenUsage

import pathlib

_FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# DDC v1 fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ddc_ecommerce() -> CustomerConfigV2:
    """Complete valid DDC for a small e-commerce store. Canonical test fixture."""
    raw = json.loads((_FIXTURES_DIR / "ddc_ecommerce.json").read_text())
    return CustomerConfigV2.model_validate(raw)


# ---------------------------------------------------------------------------
# Pipeline run / event fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_run_id() -> str:
    return "test-run-00000000-0000-0000-0000-000000000001"


@pytest.fixture
def captured_events() -> tuple[list[PipelineEvent], Callable[[PipelineEvent], None]]:
    """
    Returns a (events_list, emit_callback) pair.

    Pass the callback as emit_event to agent.execute(); inspect the list
    afterwards to assert which events were emitted in which order.
    """
    events: list[PipelineEvent] = []

    def emit(event: PipelineEvent) -> None:
        events.append(event)

    return events, emit


# ---------------------------------------------------------------------------
# Anthropic client mock
# ---------------------------------------------------------------------------

def _make_mock_response(json_payload: dict | str) -> MagicMock:
    """Build a mock Anthropic messages.create() response for a given payload."""
    if isinstance(json_payload, dict):
        text = json.dumps(json_payload)
    else:
        text = json_payload

    content_block = MagicMock()
    content_block.text = text

    usage = MagicMock()
    usage.input_tokens = 100
    usage.output_tokens = 200

    response = MagicMock()
    response.content = [content_block]
    response.usage = usage
    return response


@pytest.fixture
def mock_anthropic(monkeypatch) -> MagicMock:
    """
    Patches app.agents.base.anthropic.AsyncAnthropic so that no real API
    calls are made.  Returns the mock client so tests can configure
    .messages.create return values.

    Usage:
        mock_anthropic.messages.create = AsyncMock(return_value=_make_mock_response({...}))
    """
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock()

    monkeypatch.setattr(
        "app.agents.base.anthropic.AsyncAnthropic",
        lambda **kwargs: mock_client,
    )
    return mock_client


@pytest.fixture
def make_mock_response():
    """Expose the helper so individual tests can build mock responses."""
    return _make_mock_response
