"""
Customer configuration schemas.

Defines the structure of the raw config produced by the intake form
and the finalized config produced by the Requirements Analyst.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# --- Enums for constrained fields ---

class IndustryType(str, Enum):
    RETAIL = "retail"
    FOOD_AND_BEVERAGE = "food_and_beverage"
    PROFESSIONAL_SERVICES = "professional_services"
    HEALTHCARE = "healthcare"
    EDUCATION = "education"
    MANUFACTURING = "manufacturing"
    OTHER = "other"


class BusinessSize(str, Enum):
    SOLO = "1-5"
    SMALL = "6-20"
    MEDIUM = "21-50"
    LARGE = "50+"


class UserType(str, Enum):
    OWNER = "owner"
    EMPLOYEES = "employees"
    CUSTOMERS = "customers"
    ALL = "all"


class AccessScope(str, Enum):
    PERSONAL = "just_me"
    TEAM = "team_network"
    PUBLIC = "anyone_internet"


class DesignStyle(str, Enum):
    MINIMAL = "clean_minimal"
    CORPORATE = "professional_corporate"
    COLORFUL = "modern_colorful"
    NO_PREFERENCE = "no_preference"


class MobileSupport(str, Enum):
    YES = "yes"
    NO = "no"
    NICE_TO_HAVE = "nice_to_have"


class DataVolume(str, Enum):
    UNDER_100 = "under_100"
    SMALL = "100-1000"
    MEDIUM = "1000-10000"
    LARGE = "10000+"


# --- Form section models ---

class BusinessContext(BaseModel):
    """Section 1: Business context information."""
    name: str = Field(..., description="Business name")
    industry: IndustryType = Field(..., description="Industry sector")
    industry_other: Optional[str] = Field(None, description="Specify if industry is 'other'")
    description: str = Field(..., description="Brief business description (2-3 sentences)")
    size: BusinessSize = Field(..., description="Number of employees")


class ProblemStatement(BaseModel):
    """Section 2: What problem the software should solve."""
    problem: str = Field(..., description="Description of the problem to solve")
    users: list[UserType] = Field(..., min_length=1, description="Who will use this software")
    current_process: Optional[str] = Field(None, description="How this is currently handled")


class FeatureRequest(BaseModel):
    """A single requested feature with priority."""
    description: str = Field(..., description="Feature description")
    priority: int = Field(..., ge=1, description="Priority rank (1 = highest)")
    feature_id: str = Field("", description="Stable server-generated feature identifier (filled at POST /start)")


class Features(BaseModel):
    """Section 3: Core feature requests."""
    requested: list[FeatureRequest] = Field(..., min_length=1, description="List of requested features")


class FileUpload(BaseModel):
    """Reference to an uploaded file."""
    filename: str
    category: str = Field(..., description="Upload category: existing_data | reference_spreadsheet | sample_document | branding_material | design_reference")
    file_path: Optional[str] = Field(None, description="Server-side file path after upload")


class DataRequirements(BaseModel):
    """Section 4: Data and content requirements."""
    entities: str = Field(..., description="What information needs to be stored")
    has_existing_data: bool = Field(False, description="Whether existing data needs importing")
    uploads: list[FileUpload] = Field(default_factory=list, description="Uploaded files")
    volume: DataVolume = Field(DataVolume.UNDER_100, description="Estimated data volume")


class DesignPreferences(BaseModel):
    """Section 5: Design and branding preferences (all optional)."""
    colors: Optional[list[str]] = Field(None, description="Brand colors (hex values)")
    logo: Optional[FileUpload] = Field(None, description="Uploaded logo file")
    references: list[FileUpload] = Field(default_factory=list, description="Design reference uploads")
    style: DesignStyle = Field(DesignStyle.NO_PREFERENCE, description="Preferred visual style")


class TechnicalRequirements(BaseModel):
    """Section 6: Technical requirements (constrained choices)."""
    access_scope: AccessScope = Field(AccessScope.PUBLIC, description="Who needs access")
    auth_required: bool = Field(True, description="Whether user login is needed")
    user_roles: Optional[str] = Field(None, description="User roles if auth is required")
    mobile: MobileSupport = Field(MobileSupport.NICE_TO_HAVE, description="Mobile support level")


class ProjectMeta(BaseModel):
    """Section 7: Timeline and additional info."""
    deadline: Optional[datetime] = Field(None, description="Hard deadline if any")
    notes: Optional[str] = Field(None, description="Additional notes")
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# --- Top-level config models ---

class CustomerConfig(BaseModel):
    """
    Raw customer configuration produced by the intake form.
    This is the input to the Requirements Analyst agent.
    """
    business_context: BusinessContext
    problem_statement: ProblemStatement
    features: Features
    data: DataRequirements
    design: DesignPreferences = Field(default_factory=DesignPreferences)
    technical: TechnicalRequirements = Field(default_factory=TechnicalRequirements)
    meta: ProjectMeta = Field(default_factory=ProjectMeta)


class AssumedField(BaseModel):
    """A field where the Requirements Analyst made an assumption."""
    field_path: str = Field(..., description="Dot-path to the field, e.g. 'features.requested[0].description'")
    original_value: Optional[str] = Field(None, description="What the customer originally provided")
    assumed_value: str = Field(..., description="What the agent assumed")
    reasoning: str = Field(..., description="Why this assumption was made")


class ClarificationQuestion(BaseModel):
    """A question the Requirements Analyst needs answered."""
    id: str = Field(..., description="Unique question identifier")
    topic: str = Field(..., description="Topic category for grouping")
    original_input: str = Field(..., description="The customer input being clarified")
    question: str = Field(..., description="The clarification question")
    suggestions: list[str] = Field(default_factory=list, description="2-3 suggested answers")


class ClarificationRound(BaseModel):
    """A single round of clarification questions and answers."""
    round_number: int
    questions: list[ClarificationQuestion]
    answers: Optional[dict[str, str]] = Field(None, description="Customer answers keyed by question id")


class FinalizedConfig(BaseModel):
    """
    The finalized, unambiguous customer configuration.
    Produced by the Requirements Analyst after the clarification loop.
    This is the canonical reference for ALL downstream agents.
    """
    config: CustomerConfig = Field(..., description="The complete, validated config")
    assumptions: list[AssumedField] = Field(default_factory=list, description="Any assumptions made")
    clarification_history: list[ClarificationRound] = Field(default_factory=list)
    project_summary: str = Field(..., description="Human-readable project brief for the customer")
    is_complete: bool = Field(..., description="Whether the config is fully specified")
