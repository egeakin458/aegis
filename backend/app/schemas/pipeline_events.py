"""
Pipeline event schemas.

Defines the event format for SSE streaming to the frontend
and for SQLite logging for evaluation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class AgentName(str, Enum):
    REQUIREMENTS_ANALYST = "requirements_analyst"
    SOLUTION_ARCHITECT = "solution_architect"
    DEVELOPER = "developer"
    QA_REVIEWER = "qa_reviewer"
    SYSTEM = "system"


class EventType(str, Enum):
    # Pipeline lifecycle
    PIPELINE_STARTED = "pipeline_started"
    PIPELINE_COMPLETE = "pipeline_complete"
    PIPELINE_PARTIAL = "pipeline_partial"
    PIPELINE_FAILED = "pipeline_failed"

    # Agent lifecycle
    AGENT_START = "agent_start"
    AGENT_COMPLETE = "agent_complete"

    # LLM interaction
    LLM_CALL_START = "llm_call_start"
    LLM_CALL_COMPLETE = "llm_call_complete"

    # Clarification loop
    CLARIFICATION_NEEDED = "clarification_needed"
    CLARIFICATION_RECEIVED = "clarification_received"
    CONFIG_FINALIZED = "config_finalized"

    # Feedback loops
    REVISION_REQUESTED = "revision_requested"
    REVISION_STARTED = "revision_started"

    # Validation
    VALIDATION_PASSED = "validation_passed"
    VALIDATION_FAILED = "validation_failed"

    # Progress updates
    FILE_GENERATED = "file_generated"
    PROGRESS_UPDATE = "progress_update"

    # Errors
    ERROR = "error"


class PipelineState(str, Enum):
    """States of the pipeline state machine."""
    INTAKE = "intake"
    REQUIREMENTS = "requirements"
    CLARIFICATION = "clarification"
    DESIGN = "design"
    DEVELOPMENT = "development"
    REVIEW = "review"
    CODE_REVISION = "code_revision"
    DESIGN_REVISION = "design_revision"
    COMPLETE = "complete"
    FAILED = "failed"


class TokenUsage(BaseModel):
    """Token usage for a single LLM call."""
    input_tokens: int = 0
    output_tokens: int = 0


class PipelineEvent(BaseModel):
    """
    A single event in the pipeline execution.
    Emitted via SSE to the frontend and persisted to SQLite.
    """
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    agent: AgentName
    event_type: EventType
    message: str = Field(..., description="Human-readable, business-language message for the UI")
    data: dict[str, Any] = Field(default_factory=dict, description="Event-specific payload")
    tokens_used: Optional[TokenUsage] = None
    duration_ms: Optional[int] = None
    pipeline_state: Optional[PipelineState] = None

    def to_sse(self) -> str:
        """Serialize to SSE event format."""
        return self.model_dump_json()


class PipelineRun(BaseModel):
    """
    Complete record of a pipeline execution.
    Used for evaluation and process fidelity analysis.
    """
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    state: PipelineState = PipelineState.INTAKE
    task_id: Optional[str] = Field(None, description="Benchmark task ID if this is an evaluation run")
    events: list[PipelineEvent] = Field(default_factory=list)
    total_tokens: TokenUsage = Field(default_factory=TokenUsage)
    total_duration_ms: int = 0
    total_cost_usd: float = 0.0
    outcome: Optional[str] = Field(None, description="success | partial | failed")
    feedback_cycles: dict[str, int] = Field(
        default_factory=lambda: {"code_revisions": 0, "design_revisions": 0}
    )
