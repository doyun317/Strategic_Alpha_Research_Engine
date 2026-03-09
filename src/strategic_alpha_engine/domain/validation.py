from __future__ import annotations

import re
from datetime import datetime

from pydantic import Field, field_validator, model_validator

from strategic_alpha_engine.domain.base import EngineModel
from strategic_alpha_engine.domain.common import IDENTIFIER_PATTERN, ensure_unique_sequence
from strategic_alpha_engine.domain.enums import SimulationStatus, ValidationStage

_PERIOD_PATTERN = re.compile(r"^P(?:\d+Y)?(?:\d+M)?(?:\d+D)?$")


def _require_timezone_aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


class ValidationRecord(EngineModel):
    validation_id: str = Field(pattern=IDENTIFIER_PATTERN)
    candidate_id: str = Field(pattern=IDENTIFIER_PATTERN)
    hypothesis_id: str = Field(pattern=IDENTIFIER_PATTERN)
    blueprint_id: str = Field(pattern=IDENTIFIER_PATTERN)
    source_run_id: str = Field(pattern=IDENTIFIER_PATTERN)
    candidate_source_run_id: str = Field(pattern=IDENTIFIER_PATTERN)
    validation_stage: ValidationStage = ValidationStage.STAGE_B
    period: str = Field(min_length=2, max_length=32)
    status: SimulationStatus
    sharpe: float | None = None
    fitness: float | None = None
    turnover: float | None = None
    returns: float | None = None
    drawdown: float | None = None
    checks: list[str] = Field(default_factory=list, max_length=24)
    grade: str = Field(min_length=1, max_length=32)
    pass_decision: bool
    reasons: list[str] = Field(default_factory=list, max_length=16)
    validated_at: datetime

    @field_validator("period")
    @classmethod
    def validate_period(cls, value: str) -> str:
        if not _PERIOD_PATTERN.fullmatch(value) or not any(char.isdigit() for char in value):
            raise ValueError("period must use an ISO-8601 period shape like P3Y0M0D")
        return value

    @field_validator("checks", "reasons")
    @classmethod
    def validate_text_lists(cls, value: list[str], info) -> list[str]:
        return ensure_unique_sequence(value, info.field_name)

    @field_validator("validated_at")
    @classmethod
    def validate_validated_at(cls, value: datetime) -> datetime:
        return _require_timezone_aware(value, "validated_at")

    @model_validator(mode="after")
    def validate_result_shape(self) -> "ValidationRecord":
        metrics = (self.sharpe, self.fitness, self.turnover, self.returns, self.drawdown)

        if self.status == SimulationStatus.SUCCEEDED and any(metric is None for metric in metrics):
            raise ValueError("successful validation records must include all core metrics")
        if self.pass_decision and self.status != SimulationStatus.SUCCEEDED:
            raise ValueError("pass_decision can only be true when validation status succeeded")
        if self.pass_decision and self.grade.upper() in {"D", "F"}:
            raise ValueError("passing validation records must not use a failing grade")
        return self
