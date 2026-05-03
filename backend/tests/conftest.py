"""
Shared pytest fixtures for the Aegis backend test suite.
"""

from __future__ import annotations

import json
from typing import Callable
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.customer_config import (
    BusinessContext,
    BusinessSize,
    CustomerConfig,
    DataRequirements,
    FeatureRequest,
    Features,
    FinalizedConfig,
    IndustryType,
    ProblemStatement,
    UserType,
    AssumedField,
    ClarificationQuestion,
    ClarificationRound,
)
from app.schemas.pipeline_events import PipelineEvent, TokenUsage
from app.schemas.customer_config_v2 import CustomerConfigV2

import pathlib

_FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Customer config fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def valid_customer_config() -> CustomerConfig:
    """Minimal valid CustomerConfig that passes all schema validation."""
    return CustomerConfig(
        business_context=BusinessContext(
            name="Cafe Latte",
            industry=IndustryType.FOOD_AND_BEVERAGE,
            description="A small coffee shop chain with 3 locations.",
            size=BusinessSize.SMALL,
        ),
        problem_statement=ProblemStatement(
            problem="We need an online ordering system for pickup orders.",
            users=[UserType.CUSTOMERS, UserType.EMPLOYEES],
            current_process="Phone calls and walk-ins only.",
        ),
        features=Features(
            requested=[
                FeatureRequest(description="Menu display with categories", priority=1, feature_id="feat_menu-display-with-categories_a1b2c3"),
                FeatureRequest(description="Shopping cart and checkout", priority=2, feature_id="feat_shopping-cart-and-checkout_d4e5f6"),
            ]
        ),
        data=DataRequirements(entities=[
            {"name": "MenuItem", "description": "A single item on the cafe menu", "estimated_volume": None},
            {"name": "Order", "description": "A customer order", "estimated_volume": None},
            {"name": "Customer", "description": "A registered customer", "estimated_volume": None},
        ]),
    )


@pytest.fixture
def valid_finalized_config(valid_customer_config: CustomerConfig) -> FinalizedConfig:
    """Minimal valid FinalizedConfig wrapping the base customer config."""
    return FinalizedConfig(
        config=valid_customer_config,
        assumptions=[
            AssumedField(
                field_path="technical.auth_required",
                original_value=None,
                assumed_value="true",
                reasoning="Customers need accounts to track orders.",
            ),
        ],
        project_summary=(
            "An online ordering system for Cafe Latte, a 3-location coffee shop. "
            "Customers can browse the menu and place pickup orders. "
            "Staff can manage incoming orders in real time."
        ),
        is_complete=True,
    )


@pytest.fixture
def sample_clarification_question() -> ClarificationQuestion:
    return ClarificationQuestion(
        id="q1",
        topic="authentication",
        original_input="Need an online ordering system",
        question="Should customers be required to create an account before ordering?",
        suggestions=["Yes, always", "No, allow guest checkout", "Optional"],
    )


@pytest.fixture
def sample_clarification_round(
    sample_clarification_question: ClarificationQuestion,
) -> ClarificationRound:
    return ClarificationRound(
        round_number=1,
        questions=[sample_clarification_question],
        answers={"q1": "Yes, always"},
    )


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


@pytest.fixture
def use_legacy_mode(monkeypatch):
    """Force use_ddc=False so legacy-path tests keep working after C14 flag flip."""
    from app.config import settings as _settings
    monkeypatch.setattr(_settings, "use_ddc", False)
