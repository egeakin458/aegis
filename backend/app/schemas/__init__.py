"""
Aegis schema definitions.

All data contracts for the pipeline are defined here.
Import from this package for clean access to all schemas.
"""

from .customer_config import (
    Actor,
    Attribute,
    BusinessRule,
    ClarificationQuestion,
    ClarificationRound,
    CustomerConfigV2,
    DomainEntity,
    ProjectContext,
    Relationship,
    UseCase,
    SCHEMA_VERSION as DDC_SCHEMA_VERSION,
)
from .agent_outputs import (
    APIEndpoint,
    CodeFile,
    CodeOutput,
    DataField,
    DataModel,
    FileSpec,
    IssueSeverity,
    QAReview,
    ReviewIssue,
    ReviewVerdict,
    TechnicalDesign,
    UIComponent,
)
from .pipeline_events import (
    AgentName,
    EventType,
    PipelineEvent,
    PipelineRun,
    PipelineState,
    TokenUsage,
)
from .ra_output import (
    RAOutputDDC,
)
from .evaluation import (
    BenchmarkTask,
    BetaFeedback,
    ComplexityTier,
    EvaluationResult,
    JudgeScore,
)

__all__ = [
    # Agent outputs
    "TechnicalDesign",
    "DataModel",
    "DataField",
    "APIEndpoint",
    "UIComponent",
    "FileSpec",
    "CodeOutput",
    "CodeFile",
    "QAReview",
    "ReviewIssue",
    "ReviewVerdict",
    "IssueSeverity",
    # DDC v1 schema
    "CustomerConfigV2",
    "ProjectContext",
    "Actor",
    "DomainEntity",
    "Attribute",
    "Relationship",
    "BusinessRule",
    "UseCase",
    "ClarificationQuestion",
    "ClarificationRound",
    "DDC_SCHEMA_VERSION",
    # RA output wrapper
    "RAOutputDDC",
    # Pipeline events
    "PipelineEvent",
    "PipelineRun",
    "PipelineState",
    "EventType",
    "AgentName",
    "TokenUsage",
    # Evaluation
    "BenchmarkTask",
    "EvaluationResult",
    "JudgeScore",
    "BetaFeedback",
    "ComplexityTier",
]
