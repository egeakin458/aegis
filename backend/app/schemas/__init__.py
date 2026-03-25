"""
Aegis schema definitions.

All data contracts for the pipeline are defined here.
Import from this package for clean access to all schemas.
"""

from .customer_config import (
    AccessScope,
    AssumedField,
    BusinessContext,
    BusinessSize,
    ClarificationQuestion,
    ClarificationRound,
    CustomerConfig,
    DataRequirements,
    DataVolume,
    DesignPreferences,
    DesignStyle,
    FeatureRequest,
    Features,
    FileUpload,
    FinalizedConfig,
    IndustryType,
    MobileSupport,
    ProblemStatement,
    ProjectMeta,
    TechnicalRequirements,
    UserType,
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
    RAOutput,
)
from .evaluation import (
    BenchmarkTask,
    BetaFeedback,
    ComplexityTier,
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
    # Customer config enums
    "IndustryType",
    "BusinessSize",
    "UserType",
    "AccessScope",
    "DesignStyle",
    "MobileSupport",
    "DataVolume",
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
    # RA output wrapper
    "RAOutput",
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
