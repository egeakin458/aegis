"""
Aegis schema definitions.

All data contracts for the pipeline are defined here.
Import from this package for clean access to all schemas.
"""

from .customer_config import (
    AssumedField,
    BusinessContext,
    ClarificationQuestion,
    ClarificationRound,
    CustomerConfig,
    DataRequirements,
    DesignPreferences,
    FeatureRequest,
    Features,
    FileUpload,
    FinalizedConfig,
    ProblemStatement,
    ProjectMeta,
    TechnicalRequirements,
)
from .agent_outputs import (
    APIEndpoint,
    CodeFile,
    CodeOutput,
    DataField,
    DataModel,
    FileSpec,
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
from .evaluation import (
    BenchmarkTask,
    BetaFeedback,
    EvaluationResult,
    JudgeScore,
)

__all__ = [
    # Customer config
    "CustomerConfig",
    "FinalizedConfig",
    "BusinessContext",
    "ProblemStatement",
    "Features",
    "FeatureRequest",
    "DataRequirements",
    "DesignPreferences",
    "TechnicalRequirements",
    "ProjectMeta",
    "FileUpload",
    "ClarificationQuestion",
    "ClarificationRound",
    "AssumedField",
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
]
