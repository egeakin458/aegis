"""
Requirements Analyst output schema.

The RA is unique among Aegis agents because it produces two different
output shapes depending on whether clarification is needed:
- Clarification needed: questions for the customer
- No clarification / finalization: a complete FinalizedConfig

This wrapper schema handles both cases with a discriminator on `needs_clarification`.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, model_validator

from .customer_config import (
    ClarificationQuestion,
    CustomerConfig,
    FinalizedConfig,
)
from .customer_config_v2 import CustomerConfigV2


class RAOutput(BaseModel):
    """
    Output of the Requirements Analyst agent.

    When needs_clarification is True:
        - questions must be provided (1-10 items)
        - finalized_config must be None

    When needs_clarification is False:
        - finalized_config must be provided
        - questions must be empty or None
    """
    needs_clarification: bool = Field(
        ..., description="Whether the customer needs to answer clarification questions"
    )
    reasoning: str = Field(
        ..., description="Agent's analytical reasoning about the customer's input"
    )
    questions: Optional[list[ClarificationQuestion]] = Field(
        None, description="Clarification questions when needs_clarification is true"
    )
    finalized_config: Optional[FinalizedConfig] = Field(
        None, description="Finalized config when needs_clarification is false"
    )

    @model_validator(mode="after")
    def validate_output_consistency(self) -> RAOutput:
        if self.needs_clarification:
            if not self.questions or len(self.questions) == 0:
                raise ValueError(
                    "questions must be provided when needs_clarification is true"
                )
            if len(self.questions) > 10:
                raise ValueError(
                    "Maximum 10 questions per clarification round"
                )
        else:
            if self.finalized_config is None:
                raise ValueError(
                    "finalized_config must be provided when needs_clarification is false"
                )
        return self


class RAOutputDDC(BaseModel):
    """
    DDC-mode output of the Requirements Analyst agent.

    When needs_clarification is True:
        - questions must be provided (1-5 items)
        - finalized_config must be None

    When needs_clarification is False:
        - finalized_config must be a valid CustomerConfigV2
        - questions must be empty or None
    """
    needs_clarification: bool = Field(
        ..., description="Whether the customer needs to answer clarification questions"
    )
    reasoning: str = Field(
        ..., description="Agent's analytical reasoning about the customer's input"
    )
    questions: Optional[list[ClarificationQuestion]] = Field(
        None, description="Clarification questions when needs_clarification is true (max 5)"
    )
    finalized_config: Optional[CustomerConfigV2] = Field(
        None, description="Complete DDC when needs_clarification is false"
    )

    @model_validator(mode="after")
    def validate_output_consistency(self) -> "RAOutputDDC":
        if self.needs_clarification:
            if not self.questions or len(self.questions) == 0:
                raise ValueError(
                    "questions must be provided when needs_clarification is true"
                )
            if len(self.questions) > 5:
                raise ValueError(
                    "Maximum 5 questions per clarification round"
                )
        else:
            if self.finalized_config is None:
                raise ValueError(
                    "finalized_config must be provided when needs_clarification is false"
                )
        return self
