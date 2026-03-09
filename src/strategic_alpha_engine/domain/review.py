from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator, model_validator

from strategic_alpha_engine.domain.base import EngineModel
from strategic_alpha_engine.domain.common import IDENTIFIER_PATTERN, ensure_unique_sequence
from strategic_alpha_engine.domain.enums import (
    CandidateLifecycleStage,
    HumanReviewDecisionKind,
    ResearchFamily,
)

_REVIEWER_PATTERN = r"^[A-Za-z0-9_.@-]{3,64}$"


def _require_timezone_aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


class HumanReviewDecision(EngineModel):
    decision_id: str = Field(pattern=IDENTIFIER_PATTERN)
    queue_entry_id: str = Field(pattern=IDENTIFIER_PATTERN)
    candidate_id: str = Field(pattern=IDENTIFIER_PATTERN)
    hypothesis_id: str = Field(pattern=IDENTIFIER_PATTERN)
    blueprint_id: str = Field(pattern=IDENTIFIER_PATTERN)
    family: ResearchFamily
    source_run_id: str = Field(pattern=IDENTIFIER_PATTERN)
    submission_ready_source_run_id: str = Field(pattern=IDENTIFIER_PATTERN)
    decision: HumanReviewDecisionKind
    to_stage: CandidateLifecycleStage
    reviewer: str = Field(pattern=_REVIEWER_PATTERN)
    reasons: list[str] = Field(default_factory=list, max_length=16)
    notes: str | None = Field(default=None, max_length=240)
    reviewed_at: datetime

    @field_validator("reasons")
    @classmethod
    def validate_reasons(cls, value: list[str]) -> list[str]:
        return ensure_unique_sequence(value, "reasons")

    @field_validator("reviewed_at")
    @classmethod
    def validate_reviewed_at(cls, value: datetime) -> datetime:
        return _require_timezone_aware(value, "reviewed_at")

    @model_validator(mode="after")
    def validate_decision_shape(self) -> "HumanReviewDecision":
        expected_stage = {
            HumanReviewDecisionKind.APPROVE: CandidateLifecycleStage.SUBMISSION_READY,
            HumanReviewDecisionKind.HOLD: CandidateLifecycleStage.ROBUST_CANDIDATE,
            HumanReviewDecisionKind.REJECT: CandidateLifecycleStage.REJECTED,
        }[self.decision]
        if self.to_stage != expected_stage:
            raise ValueError("human review decisions must map to the expected candidate lifecycle stage")
        return self
