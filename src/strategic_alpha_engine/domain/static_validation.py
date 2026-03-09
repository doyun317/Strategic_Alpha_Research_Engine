from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from strategic_alpha_engine.domain.base import EngineModel
from strategic_alpha_engine.domain.common import IDENTIFIER_PATTERN


class StaticValidationIssue(EngineModel):
    code: str = Field(min_length=3, max_length=64)
    severity: str = Field(pattern=r"^(low|medium|high)$")
    message: str = Field(min_length=8, max_length=300)
    suggestion: str | None = Field(default=None, max_length=220)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().lower()


class StaticValidationReport(EngineModel):
    validation_id: str = Field(pattern=IDENTIFIER_PATTERN)
    candidate_id: str = Field(pattern=IDENTIFIER_PATTERN)
    blueprint_id: str = Field(pattern=IDENTIFIER_PATTERN)
    passes: bool
    checked_operator_count: int = Field(ge=0, le=128)
    checked_field_count: int = Field(ge=0, le=128)
    issues: list[StaticValidationIssue] = Field(default_factory=list, max_length=32)
    validator_name: str = Field(default="metadata_backed_static_validator", min_length=3, max_length=64)

    @model_validator(mode="after")
    def validate_pass_consistency(self) -> "StaticValidationReport":
        high_issues = [issue for issue in self.issues if issue.severity == "high"]
        if self.passes and high_issues:
            raise ValueError("reports with high severity issues must not pass")
        if not self.passes and not self.issues:
            raise ValueError("failing validation reports must contain at least one issue")
        return self
