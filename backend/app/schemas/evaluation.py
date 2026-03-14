"""
Evaluation schemas.

Defines structures for benchmark tasks, LLM-as-judge scoring,
and beta user feedback.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ComplexityTier(str, Enum):
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


class BenchmarkTask(BaseModel):
    """A predefined benchmark task for evaluation."""
    task_id: str
    name: str
    description: str
    complexity: ComplexityTier
    customer_config: dict = Field(..., description="Pre-filled CustomerConfig as dict")
    expected_features: list[str] = Field(..., description="Features that should be present in output")
    unit_tests: list[str] = Field(default_factory=list, description="Test descriptions for functional correctness")


class JudgeScore(BaseModel):
    """Score from a single LLM-as-judge evaluation run."""
    requirements_coverage: int = Field(..., ge=1, le=5)
    code_organization: int = Field(..., ge=1, le=5)
    documentation_quality: int = Field(..., ge=1, le=5)
    overall_coherence: int = Field(..., ge=1, le=5)
    reasoning: str = Field(..., description="Judge's reasoning for the scores")


class EvaluationResult(BaseModel):
    """Complete evaluation result for a single task."""
    task_id: str
    system: str = Field(..., description="aegis | baseline")
    judge_scores: list[JudgeScore] = Field(..., description="3 scoring runs for averaging")
    average_scores: Optional[dict[str, float]] = None
    unit_test_pass_rate: Optional[float] = None
    pipeline_run_id: Optional[str] = Field(None, description="Aegis pipeline run ID for traceability")
    tokens_used: Optional[dict[str, int]] = None
    duration_ms: Optional[int] = None
    cost_usd: Optional[float] = None
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BetaFeedback(BaseModel):
    """Structured feedback from beta evaluation."""
    evaluator: str = Field(..., description="student | supervisor")
    scenario_description: str
    output_match: int = Field(..., ge=1, le=5, description="How well output matches description")
    quality_rating: int = Field(..., ge=1, le=5, description="Quality of generated application")
    process_clarity: int = Field(..., ge=1, le=5, description="Was the agent process understandable")
    clarification_helpful: int = Field(..., ge=1, le=5, description="Was clarification process helpful")
    trust_issues: bool = Field(..., description="Were there moments of lost trust")
    trust_issues_detail: Optional[str] = None
    improvement_suggestions: Optional[str] = None
    would_use_again: bool
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
