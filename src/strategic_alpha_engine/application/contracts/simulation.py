from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field, field_validator, model_validator

from strategic_alpha_engine.domain.base import EngineModel
from strategic_alpha_engine.domain.common import IDENTIFIER_PATTERN
from strategic_alpha_engine.domain.enums import SimulationStatus

_ACTIVE_SIMULATION_STATUSES = {
    SimulationStatus.SUBMITTED,
    SimulationStatus.RUNNING,
}
_TERMINAL_SIMULATION_STATUSES = {
    SimulationStatus.SUCCEEDED,
    SimulationStatus.FAILED,
    SimulationStatus.TIMED_OUT,
}


def _require_timezone_aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


class BrainSimulationSubmission(EngineModel):
    simulation_request_id: str = Field(pattern=IDENTIFIER_PATTERN)
    provider_run_id: str = Field(min_length=3, max_length=128)
    status: SimulationStatus = Field(default=SimulationStatus.SUBMITTED)
    accepted_at: datetime
    provider_message: str | None = Field(default=None, max_length=240)

    @field_validator("accepted_at")
    @classmethod
    def validate_accepted_at(cls, value: datetime) -> datetime:
        return _require_timezone_aware(value, "accepted_at")

    @model_validator(mode="after")
    def validate_status(self) -> "BrainSimulationSubmission":
        if self.status not in _ACTIVE_SIMULATION_STATUSES:
            raise ValueError("BrainSimulationSubmission status must be submitted or running")
        return self


class BrainSimulationPollResult(EngineModel):
    provider_run_id: str = Field(min_length=3, max_length=128)
    status: SimulationStatus
    observed_at: datetime
    provider_message: str | None = Field(default=None, max_length=240)

    @field_validator("observed_at")
    @classmethod
    def validate_observed_at(cls, value: datetime) -> datetime:
        return _require_timezone_aware(value, "observed_at")

    @model_validator(mode="after")
    def validate_status(self) -> "BrainSimulationPollResult":
        if self.status == SimulationStatus.PENDING:
            raise ValueError("BrainSimulationPollResult status must not be pending")
        return self


class BrainSimulationResult(EngineModel):
    simulation_request_id: str = Field(pattern=IDENTIFIER_PATTERN)
    candidate_id: str = Field(pattern=IDENTIFIER_PATTERN)
    provider_run_id: str = Field(min_length=3, max_length=128)
    status: SimulationStatus
    completed_at: datetime
    sharpe: float | None = None
    fitness: float | None = None
    turnover: float | None = None
    returns: float | None = None
    drawdown: float | None = None
    checks: list[str] = Field(default_factory=list, max_length=16)
    grade: str | None = Field(default=None, min_length=1, max_length=32)
    raw_response: dict[str, Any] = Field(default_factory=dict)

    @field_validator("completed_at")
    @classmethod
    def validate_completed_at(cls, value: datetime) -> datetime:
        return _require_timezone_aware(value, "completed_at")

    @model_validator(mode="after")
    def validate_result_shape(self) -> "BrainSimulationResult":
        if self.status not in _TERMINAL_SIMULATION_STATUSES:
            raise ValueError("BrainSimulationResult status must be terminal")

        metrics = (self.sharpe, self.fitness, self.turnover, self.returns, self.drawdown)
        if self.status == SimulationStatus.SUCCEEDED and any(metric is None for metric in metrics):
            raise ValueError("succeeded BrainSimulationResult instances must include all core metrics")
        return self
