"""
Domain-Driven Configuration (DDC) v1 schema.

Strict 4-dimensional contract (Who / What / Why+How) that is directly
machine-actionable by all pipeline agents.
"""

from pydantic import BaseModel, Field, model_validator
from typing import List, Literal, Optional
import uuid


# --- Enums ---

AuthMethod = Literal["anonymous", "email_password", "invite_only", "sso"]
UseCaseType = Literal["command", "query"]
DataFieldType = Literal["string", "text", "integer", "decimal", "boolean", "datetime", "date", "uuid", "json"]
RelationshipKind = Literal["one_to_one", "one_to_many", "many_to_many"]
Industry = Literal["retail", "healthcare", "education", "finance", "services", "other"]
VisualStyle = Literal["clean_minimal", "bold_modern", "warm_friendly", "professional_corporate", "playful"]


# --- Atoms ---

class Attribute(BaseModel):
    """A typed property of a DomainEntity. Reuses Phase-3 typed schemas."""
    name: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$",
                      description="snake_case attribute name. Becomes a SQL column.")
    type: DataFieldType = Field(..., description="Maps directly to a SQLite column type.")
    required: bool = Field(default=True)
    unique: bool = Field(default=False)
    description: Optional[str] = Field(None, max_length=200,
                                       description="Optional human note for the SA's UI rendering.")


class Relationship(BaseModel):
    """Entity-to-entity relationship. Drives FK creation by the SA."""
    id: str = Field(default_factory=lambda: f"rel_{uuid.uuid4().hex[:8]}")
    from_entity_id: str = Field(..., description="References DomainEntity.id (the owning side).")
    to_entity_id: str = Field(..., description="References DomainEntity.id (the related side).")
    kind: RelationshipKind
    name: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$",
                      description="snake_case role name, e.g. 'order_items', 'author'.")


# --- Core Dimensions ---

class ProjectContext(BaseModel):
    name: str = Field(..., min_length=2, max_length=60,
                      description="Kebab-case basis for project naming.")
    domain_description: str = Field(..., min_length=50, max_length=1500,
                                    description="Core business value. SA infers tone and UX from this.")
    industry: Industry
    visual_style: VisualStyle = Field(default="clean_minimal",
                                      description="Tailwind theme hint for the Developer agent.")
    mobile_first: bool = Field(default=True)


class Actor(BaseModel):
    """The 'WHO'. RBAC subject."""
    id: str = Field(default_factory=lambda: f"act_{uuid.uuid4().hex[:8]}")
    role_name: str = Field(..., pattern=r"^[A-Z][a-zA-Z0-9]*$",
                           description="PascalCase role, e.g. 'SystemAdmin', 'Customer'.")
    auth_method: AuthMethod
    permissions_description: str = Field(..., min_length=10, max_length=500,
                                         description="Free-text capability summary; QA reads this.")


class DomainEntity(BaseModel):
    """The 'WHAT'. Source of truth for DDL generation."""
    id: str = Field(default_factory=lambda: f"ent_{uuid.uuid4().hex[:8]}")
    name: str = Field(..., pattern=r"^[A-Z][a-zA-Z0-9]*$",
                      description="Singular PascalCase, e.g. 'Invoice', 'PatientRecord'.")
    attributes: List[Attribute] = Field(..., min_length=1)
    states: List[str] = Field(default_factory=lambda: ["Active"], min_length=1,
                              description="Lifecycle states; mapped to a CHECK constraint.")
    owned_by_actor_id: Optional[str] = Field(None,
                                             description="References Actor.id. Implies an FK to that actor.")


class BusinessRule(BaseModel):
    """The 'WHY/HOW'. Top-level so it can be referenced by many UseCases."""
    id: str = Field(default_factory=lambda: f"rule_{uuid.uuid4().hex[:8]}")
    description: str = Field(..., min_length=10, max_length=500,
                             description="Human-readable; QA asserts against this.")
    trigger_condition: str = Field(..., max_length=300,
                                   description="e.g. 'When Order.state == Pending'.")
    enforcement_action: str = Field(..., max_length=300,
                                    description="e.g. 'Reject mutation, return 400'.")


class UseCase(BaseModel):
    """The 'HOW'. Connects an Actor to an Entity through Rules."""
    id: str = Field(default_factory=lambda: f"uc_{uuid.uuid4().hex[:8]}")
    name: str = Field(..., min_length=3, max_length=80,
                      description="Imperative verb phrase, e.g. 'Process Refund'.")
    type: UseCaseType
    actor_id: str = Field(..., description="References Actor.id.")
    primary_entity_id: str = Field(..., description="References DomainEntity.id.")
    business_rule_ids: List[str] = Field(default_factory=list,
                                          description="References BusinessRule.id values.")
    description: Optional[str] = Field(None, max_length=400,
                                       description="Optional context for the SA.")


# --- Root Payload ---

SCHEMA_VERSION = "ddc-v1"


class CustomerConfigV2(BaseModel):
    schema_version: Literal["ddc-v1"] = Field(default="ddc-v1")
    context: ProjectContext
    actors: List[Actor] = Field(..., min_length=1)
    entities: List[DomainEntity] = Field(..., min_length=1)
    relationships: List[Relationship] = Field(default_factory=list)
    business_rules: List[BusinessRule] = Field(default_factory=list)
    use_cases: List[UseCase] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_referential_integrity(self) -> "CustomerConfigV2":
        actor_ids = {a.id for a in self.actors}
        entity_ids = {e.id for e in self.entities}
        rule_ids = {r.id for r in self.business_rules}

        # Uniqueness
        if len({a.role_name for a in self.actors}) != len(self.actors):
            raise ValueError("Actor role_names must be unique.")
        if len({e.name for e in self.entities}) != len(self.entities):
            raise ValueError("Entity names must be unique.")

        # Entity ownership
        for ent in self.entities:
            if ent.owned_by_actor_id and ent.owned_by_actor_id not in actor_ids:
                raise ValueError(f"Entity {ent.name} owned_by unknown Actor: {ent.owned_by_actor_id}")
            if len({a.name for a in ent.attributes}) != len(ent.attributes):
                raise ValueError(f"Entity {ent.name} has duplicate attribute names.")

        # Relationships
        for rel in self.relationships:
            if rel.from_entity_id not in entity_ids:
                raise ValueError(f"Relationship {rel.name}: unknown from_entity_id {rel.from_entity_id}")
            if rel.to_entity_id not in entity_ids:
                raise ValueError(f"Relationship {rel.name}: unknown to_entity_id {rel.to_entity_id}")

        # Use cases
        for uc in self.use_cases:
            if uc.actor_id not in actor_ids:
                raise ValueError(f"UseCase {uc.name}: unknown actor_id {uc.actor_id}")
            if uc.primary_entity_id not in entity_ids:
                raise ValueError(f"UseCase {uc.name}: unknown primary_entity_id {uc.primary_entity_id}")
            for rid in uc.business_rule_ids:
                if rid not in rule_ids:
                    raise ValueError(f"UseCase {uc.name}: unknown business_rule_id {rid}")

        return self
