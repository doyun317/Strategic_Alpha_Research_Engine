from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from strategic_alpha_engine.domain.base import EngineModel
from strategic_alpha_engine.domain.common import IDENTIFIER_PATTERN, ensure_unique_lower_text, ensure_unique_sequence
from strategic_alpha_engine.domain.enums import (
    ExpectedDirection,
    FieldClass,
    ResearchFamily,
    ResearchHorizon,
    UpdateCadence,
)

_SLOW_FIELD_CLASSES = {FieldClass.FUNDAMENTAL, FieldClass.MACRO}
_FAST_CADENCES = {
    UpdateCadence.INTRADAY,
    UpdateCadence.DAILY,
    UpdateCadence.WEEKLY,
    UpdateCadence.EVENT_DRIVEN,
}


class HypothesisSpec(EngineModel):
    hypothesis_id: str = Field(pattern=IDENTIFIER_PATTERN)
    agenda_id: str | None = Field(default=None, pattern=IDENTIFIER_PATTERN)
    family: ResearchFamily
    thesis_name: str = Field(min_length=4, max_length=140)
    economic_rationale: str = Field(min_length=16, max_length=1000)
    expected_direction: ExpectedDirection
    horizon: ResearchHorizon
    target_region: str = Field(default="USA", min_length=2, max_length=16)
    target_universe: str = Field(default="TOP3000", min_length=2, max_length=32)
    market_context: str | None = Field(default=None, max_length=240)
    field_classes: list[FieldClass] = Field(min_length=1, max_length=6)
    preferred_update_cadences: list[UpdateCadence] = Field(default_factory=list, max_length=6)
    risk_notes: list[str] = Field(default_factory=list, max_length=8)
    evidence_requirements: list[str] = Field(default_factory=list, max_length=8)
    forbidden_patterns: list[str] = Field(default_factory=list, max_length=12)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    author: str = Field(default="system", min_length=3, max_length=64)

    @field_validator("field_classes")
    @classmethod
    def validate_field_classes(cls, value: list[FieldClass]) -> list[FieldClass]:
        return ensure_unique_sequence(value, "field_classes")

    @field_validator("preferred_update_cadences")
    @classmethod
    def validate_cadences(cls, value: list[UpdateCadence]) -> list[UpdateCadence]:
        return ensure_unique_sequence(value, "preferred_update_cadences")

    @field_validator("risk_notes", "evidence_requirements")
    @classmethod
    def validate_text_lists(cls, value: list[str], info) -> list[str]:
        return ensure_unique_sequence(value, info.field_name)

    @field_validator("forbidden_patterns")
    @classmethod
    def validate_forbidden_patterns(cls, value: list[str]) -> list[str]:
        return ensure_unique_lower_text(value, "forbidden_patterns")

    @model_validator(mode="after")
    def validate_horizon_alignment(self) -> "HypothesisSpec":
        if self.horizon != ResearchHorizon.SHORT:
            return self

        slow_only = set(self.field_classes).issubset(_SLOW_FIELD_CLASSES)
        has_fast_cadence = bool(set(self.preferred_update_cadences) & _FAST_CADENCES)
        if slow_only and not has_fast_cadence:
            raise ValueError(
                "short-horizon hypotheses must include at least one fast-moving data class "
                "or an explicit fast/event-driven update cadence"
            )
        return self

