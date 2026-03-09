from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator

from strategic_alpha_engine.domain.base import EngineModel
from strategic_alpha_engine.domain.common import IDENTIFIER_PATTERN, ensure_unique_sequence
from strategic_alpha_engine.domain.research_agenda import ResearchAgenda
from strategic_alpha_engine.domain.enums import ResearchFamily


def _require_timezone_aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


class FamilyPolicyRecommendation(EngineModel):
    family: ResearchFamily
    rank: int = Field(ge=1)
    final_score: float = Field(ge=0.0, le=1.0)
    exploit_score: float = Field(ge=0.0, le=1.0)
    exploration_bonus: float = Field(ge=0.0, le=1.0)
    risk_penalty: float = Field(ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list, max_length=12)
    latest_run_id: str | None = Field(default=None, pattern=IDENTIFIER_PATTERN)
    updated_at: datetime

    @field_validator("reasons")
    @classmethod
    def validate_reasons(cls, value: list[str]) -> list[str]:
        return ensure_unique_sequence(value, "reasons")

    @field_validator("updated_at")
    @classmethod
    def validate_updated_at(cls, value: datetime) -> datetime:
        return _require_timezone_aware(value, "updated_at")


class AgendaPriorityRecommendation(EngineModel):
    agenda_id: str = Field(pattern=IDENTIFIER_PATTERN)
    family: ResearchFamily
    agenda_name: str = Field(min_length=4, max_length=140)
    base_priority: float = Field(ge=0.0, le=1.0)
    family_score: float = Field(ge=0.0, le=1.0)
    adjusted_priority: float = Field(ge=0.0, le=1.0)
    priority_delta: float = Field(ge=-1.0, le=1.0)
    reasons: list[str] = Field(default_factory=list, max_length=16)

    @field_validator("reasons")
    @classmethod
    def validate_reasons(cls, value: list[str]) -> list[str]:
        return ensure_unique_sequence(value, "reasons")


class AgendaSelection(EngineModel):
    selected_agenda: ResearchAgenda | None = None
    agenda_recommendations: list[AgendaPriorityRecommendation] = Field(default_factory=list)
    excluded_agenda_ids: list[str] = Field(default_factory=list, max_length=64)
