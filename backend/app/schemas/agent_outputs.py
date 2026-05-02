"""
Agent output schemas.

Defines the structured output format for each agent in the pipeline.
Every agent MUST return output matching its schema — validated by Pydantic
before being passed to the next agent.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field

DataFieldType = Literal[
    "string", "integer", "float", "boolean",
    "datetime", "date", "text", "enum", "json",
]

RelationshipKind = Literal["belongs_to", "has_many", "has_one", "many_to_many"]


# ============================================================
# Requirements Analyst Output
# ============================================================
# (Defined in customer_config.py as FinalizedConfig)
# The RA outputs either ClarificationQuestions or FinalizedConfig.


# ============================================================
# Solution Architect Output
# ============================================================

class DataField(BaseModel):
    """A single field in a data model."""
    name: str
    type: DataFieldType = Field(..., description="Data type: string | integer | float | boolean | datetime | date | text | enum | json")
    required: bool = True
    description: Optional[str] = None
    constraints: Optional[str] = Field(None, description="e.g., 'unique', 'max_length:255', 'enum:active,inactive'")


class DataRelationship(BaseModel):
    """A typed relationship between two data models."""
    kind: RelationshipKind = Field(..., description="belongs_to | has_many | has_one | many_to_many")
    target_model: str = Field(..., description="Name of the related DataModel (matches DataModel.name)")
    description: Optional[str] = None


class DataModel(BaseModel):
    """A database table/collection schema."""
    name: str = Field(..., description="Model name in PascalCase, e.g., 'CustomerOrder'")
    description: str
    fields: list[DataField]
    relationships: list[DataRelationship] = Field(default_factory=list, description="Typed relationships to other models")


class APIEndpoint(BaseModel):
    """An API endpoint specification."""
    method: str = Field(..., description="HTTP method: GET | POST | PUT | DELETE")
    path: str = Field(..., description="URL path, e.g., '/api/orders'")
    description: str
    request_body: Optional[str] = Field(None, description="Expected request body description")
    response: str = Field(..., description="Expected response description")


class UIComponent(BaseModel):
    """A frontend component/page specification."""
    name: str = Field(..., description="Component name, e.g., 'OrderListPage'")
    type: str = Field(..., description="page | component | layout")
    description: str
    features: list[str] = Field(default_factory=list, description="Key features this component implements")
    data_sources: list[str] = Field(default_factory=list, description="API endpoints this component uses")


class FileSpec(BaseModel):
    """A file in the project structure."""
    path: str = Field(..., description="Relative file path, e.g., 'src/pages/OrderList.jsx'")
    purpose: str = Field(..., description="What this file does")


class TechnicalDesign(BaseModel):
    """
    Output of the Solution Architect agent.
    A complete technical design document that the Developer can implement
    without creative interpretation.
    """
    reasoning: str = Field(..., description="Architect's reasoning about design decisions")
    project_name: str = Field(..., description="Application name in kebab-case")
    tech_summary: str = Field(..., description="Brief description of technologies used in the generated app")
    data_models: list[DataModel] = Field(..., min_length=1)
    api_endpoints: list[APIEndpoint] = Field(..., min_length=1)
    ui_components: list[UIComponent] = Field(..., min_length=1)
    file_structure: list[FileSpec] = Field(..., min_length=1)
    dependencies: list[str] = Field(default_factory=list, description="NPM/pip packages the generated app needs")
    notes: Optional[str] = Field(None, description="Any additional design notes or warnings")


# ============================================================
# Developer Output
# ============================================================

class CodeFile(BaseModel):
    """A single generated code file."""
    path: str = Field(..., description="Relative file path matching the design's file structure")
    content: str = Field(..., description="Complete file content")
    language: str = Field(..., description="Programming language: javascript | python | html | css | json | sql | markdown")
    description: str = Field(..., description="Human-readable description of what this file does")


class FeatureImplementation(BaseModel):
    """A single implemented feature, linked to its feature_id."""
    feature_id: str = Field(..., description="Matches FeatureRequest.feature_id from FinalizedConfig")
    description: str = Field(..., description="Human-readable feature description")
    implementation_notes: Optional[str] = Field(None, description="How the feature was implemented")


class CodeOutput(BaseModel):
    """
    Output of the Developer agent.
    A complete, structured collection of code files forming a runnable project.
    """
    reasoning: str = Field(..., description="Developer's reasoning about implementation decisions")
    project_name: str = Field(..., description="Application name in kebab-case, must match TechnicalDesign.project_name")
    files: list[CodeFile] = Field(..., min_length=1)
    setup_instructions: str = Field(..., description="How to install dependencies and run the project")
    features_implemented: list[FeatureImplementation] = Field(..., description="List of features implemented, each citing the feature_id from FinalizedConfig")
    known_limitations: list[str] = Field(default_factory=list, description="Any features that were simplified or omitted")


# ============================================================
# QA Reviewer Output
# ============================================================

class IssueSeverity(str, Enum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    SUGGESTION = "suggestion"


class ReviewVerdict(str, Enum):
    APPROVE = "approve"
    REVISE_CODE = "revise_code"
    REVISE_DESIGN = "revise_design"


class ReviewIssue(BaseModel):
    """A single issue found during QA review."""
    id: str
    severity: IssueSeverity
    category: str = Field(..., description="functional | requirements_alignment | code_quality | security")
    affected_file: Optional[str] = Field(None, description="File path where the issue was found")
    description: str = Field(..., description="Clear description of the issue")
    suggestion: str = Field(..., description="Specific, actionable fix suggestion")


class FeatureCoverage(BaseModel):
    """Coverage status for a single feature, keyed by feature_id."""
    feature_id: str = Field(..., description="Matches FeatureRequest.feature_id from FinalizedConfig")
    implemented: bool = Field(..., description="Whether the feature was implemented")
    evidence: Optional[str] = Field(None, description="Brief evidence or reason for the coverage decision")


class QAReview(BaseModel):
    """
    Output of the QA Reviewer agent.
    A structured review report with issues and a verdict.
    """
    reasoning: str = Field(..., description="Reviewer's overall assessment reasoning")
    verdict: ReviewVerdict = Field(..., description="approve | revise_code | revise_design")
    issues: list[ReviewIssue] = Field(default_factory=list)
    requirements_coverage: list[FeatureCoverage] = Field(
        default_factory=list,
        description="Coverage status for each feature from FinalizedConfig, keyed by feature_id"
    )
    code_quality_score: int = Field(..., ge=1, le=5, description="Overall code quality rating 1-5")
    summary: str = Field(..., description="Human-readable review summary for the UI")
