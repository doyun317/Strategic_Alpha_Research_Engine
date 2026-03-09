from __future__ import annotations

from pydantic import Field, field_validator

from strategic_alpha_engine.domain.base import EngineModel
from strategic_alpha_engine.domain.common import IDENTIFIER_PATTERN, ensure_unique_lower_text, ensure_unique_sequence
from strategic_alpha_engine.domain.enums import ResearchFamily, ResearchHorizon


class ResearchAgenda(EngineModel):
    agenda_id: str = Field(pattern=IDENTIFIER_PATTERN)
    name: str = Field(min_length=4, max_length=140)
    family: ResearchFamily
    priority: float = Field(default=0.5, ge=0.0, le=1.0)
    target_region: str = Field(default="USA", min_length=2, max_length=16)
    target_universe: str = Field(default="TOP3000", min_length=2, max_length=32)
    target_horizons: list[ResearchHorizon] = Field(min_length=1, max_length=3)
    motivation: str = Field(min_length=16, max_length=500)
    constraints: list[str] = Field(default_factory=list, max_length=8)
    tags: list[str] = Field(default_factory=list, max_length=8)
    owner: str = Field(default="system", min_length=3, max_length=64)
    status: str = Field(default="active", pattern=r"^(active|paused|backlog|completed)$")

    @field_validator("target_horizons")
    @classmethod
    def validate_target_horizons(cls, value: list[ResearchHorizon]) -> list[ResearchHorizon]:
        return ensure_unique_sequence(value, "target_horizons")

    @field_validator("constraints")
    @classmethod
    def validate_constraints(cls, value: list[str]) -> list[str]:
        return ensure_unique_sequence(value, "constraints")

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: list[str]) -> list[str]:
        return ensure_unique_lower_text(value, "tags")

