from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from strategic_alpha_engine.domain.base import EngineModel
from strategic_alpha_engine.domain.common import IDENTIFIER_PATTERN, ensure_unique_lower_text, ensure_unique_sequence


class CritiqueIssue(EngineModel):
    code: str = Field(min_length=3, max_length=64)
    severity: str = Field(pattern=r"^(low|medium|high)$")
    message: str = Field(min_length=8, max_length=300)
    suggestion: str | None = Field(default=None, max_length=220)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().lower()


class CritiqueReport(EngineModel):
    critique_id: str = Field(pattern=IDENTIFIER_PATTERN)
    candidate_id: str = Field(pattern=IDENTIFIER_PATTERN)
    blueprint_id: str = Field(pattern=IDENTIFIER_PATTERN)
    passes: bool
    overall_score: float = Field(ge=0.0, le=1.0)
    structural_quality_score: float = Field(ge=0.0, le=1.0)
    economic_coherence_score: float = Field(ge=0.0, le=1.0)
    data_horizon_alignment_score: float = Field(ge=0.0, le=1.0)
    issues: list[CritiqueIssue] = Field(default_factory=list, max_length=16)
    repair_suggestions: list[str] = Field(default_factory=list, max_length=16)
    tags: list[str] = Field(default_factory=list, max_length=12)
    critic_name: str = Field(default="rule_based_strategic_critic", min_length=3, max_length=64)

    @field_validator("repair_suggestions")
    @classmethod
    def validate_repair_suggestions(cls, value: list[str]) -> list[str]:
        return ensure_unique_sequence(value, "repair_suggestions")

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: list[str]) -> list[str]:
        return ensure_unique_lower_text(value, "tags")

    @model_validator(mode="after")
    def validate_pass_consistency(self) -> "CritiqueReport":
        high_issues = [issue for issue in self.issues if issue.severity == "high"]
        if self.passes and high_issues:
            raise ValueError("reports with high severity issues must not pass")
        return self

