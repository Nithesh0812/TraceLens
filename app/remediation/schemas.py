
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FixProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)

    description: str = Field(min_length=1, max_length=2000)

    rationale: str = Field(min_length=1, max_length=2000)

    confidence: Literal["low", "medium", "high"]

    risk_level: Literal["low", "medium", "high"]

    evidence_ids: list[int] = Field(default_factory=list)

    proposed_steps: list[str] = Field(default_factory=list)

    validation_steps: list[str] = Field(default_factory=list)

    rollback_steps: list[str] = Field(default_factory=list)


class FixProposalResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident_id: str

    status: Literal["proposed", "needs_more_evidence"]

    proposal: FixProposal | None = None

    warnings: list[str] = Field(default_factory=list)

    requires_human_review: bool = True
