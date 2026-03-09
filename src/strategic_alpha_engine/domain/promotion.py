from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator, model_validator

from strategic_alpha_engine.domain.base import EngineModel
from strategic_alpha_engine.domain.common import IDENTIFIER_PATTERN, ensure_unique_sequence
from strategic_alpha_engine.domain.enums import CandidateLifecycleStage, PromotionDecisionKind


def _require_timezone_aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


class PromotionDecision(EngineModel):
    promotion_id: str = Field(pattern=IDENTIFIER_PATTERN)
    candidate_id: str = Field(pattern=IDENTIFIER_PATTERN)
    hypothesis_id: str = Field(pattern=IDENTIFIER_PATTERN)
    blueprint_id: str = Field(pattern=IDENTIFIER_PATTERN)
    evaluation_id: str = Field(pattern=IDENTIFIER_PATTERN)
    source_run_id: str = Field(pattern=IDENTIFIER_PATTERN)
    from_stage: CandidateLifecycleStage
    to_stage: CandidateLifecycleStage
    decision: PromotionDecisionKind
    reasons: list[str] = Field(default_factory=list, max_length=16)
    decided_at: datetime

    @field_validator("reasons")
    @classmethod
    def validate_reasons(cls, value: list[str]) -> list[str]:
        return ensure_unique_sequence(value, "reasons")

    @field_validator("decided_at")
    @classmethod
    def validate_decided_at(cls, value: datetime) -> datetime:
        return _require_timezone_aware(value, "decided_at")

    @model_validator(mode="after")
    def validate_decision_shape(self) -> "PromotionDecision":
        if self.decision == PromotionDecisionKind.PROMOTE:
            if self.to_stage == self.from_stage or self.to_stage == CandidateLifecycleStage.REJECTED:
                raise ValueError("promote decisions must move the candidate to a later non-rejected stage")
            return self

        if self.decision == PromotionDecisionKind.REJECT:
            if self.to_stage != CandidateLifecycleStage.REJECTED:
                raise ValueError("reject decisions must move the candidate to rejected")
            return self

        if self.to_stage != self.from_stage:
            raise ValueError("hold decisions must keep the candidate at the same stage")
        return self
