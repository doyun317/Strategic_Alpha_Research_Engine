from __future__ import annotations

import re
from datetime import datetime

from pydantic import ConfigDict, Field, field_validator, model_validator

from strategic_alpha_engine.domain.base import EngineModel
from strategic_alpha_engine.domain.common import IDENTIFIER_PATTERN
from strategic_alpha_engine.domain.enums import SimulationStatus

_TEST_PERIOD_PATTERN = re.compile(r"^P(?:\d+Y)?(?:\d+M)?(?:\d+D)?$")
_TERMINAL_SIMULATION_STATUSES = {
    SimulationStatus.SUCCEEDED,
    SimulationStatus.FAILED,
    SimulationStatus.TIMED_OUT,
}


def _normalize_expression(expression: str) -> str:
    return " ".join(expression.split())


def _require_timezone_aware(value: datetime | None, field_name: str) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


class SimulationRequest(EngineModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=True,
        frozen=True,
    )

    simulation_request_id: str = Field(pattern=IDENTIFIER_PATTERN)
    candidate_id: str = Field(pattern=IDENTIFIER_PATTERN)
    hypothesis_id: str = Field(pattern=IDENTIFIER_PATTERN)
    blueprint_id: str = Field(pattern=IDENTIFIER_PATTERN)
    expression: str = Field(min_length=4, max_length=500)
    region: str = Field(default="USA", min_length=2, max_length=16)
    universe: str = Field(default="TOP3000", min_length=2, max_length=32)
    delay: int = Field(default=1, ge=0, le=10)
    neutralization: str = Field(default="subindustry", min_length=2, max_length=64)
    test_period: str = Field(default="P1Y0M0D", min_length=2, max_length=32)

    @field_validator("expression")
    @classmethod
    def validate_expression(cls, value: str) -> str:
        normalized = _normalize_expression(value)
        if normalized.count("(") != normalized.count(")"):
            raise ValueError("expression must contain balanced parentheses")
        return normalized

    @field_validator("test_period")
    @classmethod
    def validate_test_period(cls, value: str) -> str:
        if not _TEST_PERIOD_PATTERN.fullmatch(value) or not any(char.isdigit() for char in value):
            raise ValueError("test_period must use an ISO-8601 period shape like P1Y0M0D")
        return value


class SimulationRun(EngineModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=True,
        frozen=True,
    )

    simulation_run_id: str = Field(pattern=IDENTIFIER_PATTERN)
    simulation_request_id: str = Field(pattern=IDENTIFIER_PATTERN)
    candidate_id: str = Field(pattern=IDENTIFIER_PATTERN)
    region: str = Field(min_length=2, max_length=16)
    universe: str = Field(min_length=2, max_length=32)
    delay: int = Field(ge=0, le=10)
    neutralization: str = Field(min_length=2, max_length=64)
    test_period: str = Field(min_length=2, max_length=32)
    status: SimulationStatus = Field(default=SimulationStatus.PENDING)
    submitted_at: datetime | None = Field(default=None)
    completed_at: datetime | None = Field(default=None)
    provider_run_id: str | None = Field(default=None, min_length=3, max_length=128)

    @field_validator("submitted_at", "completed_at")
    @classmethod
    def validate_timestamps(cls, value: datetime | None, info) -> datetime | None:
        return _require_timezone_aware(value, info.field_name)

    @field_validator("test_period")
    @classmethod
    def validate_test_period(cls, value: str) -> str:
        if not _TEST_PERIOD_PATTERN.fullmatch(value) or not any(char.isdigit() for char in value):
            raise ValueError("test_period must use an ISO-8601 period shape like P1Y0M0D")
        return value

    @model_validator(mode="after")
    def validate_status_shape(self) -> "SimulationRun":
        terminal_statuses = {status.value for status in _TERMINAL_SIMULATION_STATUSES}

        if self.status == SimulationStatus.PENDING:
            if self.submitted_at is not None or self.completed_at is not None or self.provider_run_id is not None:
                raise ValueError("pending simulation runs must not include provider or timestamp fields")
            return self

        if self.status in {SimulationStatus.SUBMITTED, SimulationStatus.RUNNING}:
            if self.submitted_at is None or self.provider_run_id is None:
                raise ValueError(
                    "submitted or running simulation runs must include submitted_at and provider_run_id"
                )
            if self.completed_at is not None:
                raise ValueError("submitted or running simulation runs must not include completed_at")
            return self

        if self.status in terminal_statuses:
            if self.submitted_at is None or self.completed_at is None or self.provider_run_id is None:
                raise ValueError(
                    "terminal simulation runs must include submitted_at, completed_at, and provider_run_id"
                )
            if self.completed_at < self.submitted_at:
                raise ValueError("completed_at must be greater than or equal to submitted_at")
            return self

        raise ValueError(f"unsupported simulation status: {self.status}")

    @classmethod
    def from_request(cls, simulation_run_id: str, request: SimulationRequest) -> "SimulationRun":
        return cls(
            simulation_run_id=simulation_run_id,
            simulation_request_id=request.simulation_request_id,
            candidate_id=request.candidate_id,
            region=request.region,
            universe=request.universe,
            delay=request.delay,
            neutralization=request.neutralization,
            test_period=request.test_period,
        )

    def mark_submitted(self, provider_run_id: str, submitted_at: datetime) -> "SimulationRun":
        self._ensure_transition_allowed({SimulationStatus.PENDING}, SimulationStatus.SUBMITTED)
        return self._validated_copy(
            status=SimulationStatus.SUBMITTED,
            provider_run_id=provider_run_id,
            submitted_at=submitted_at,
        )

    def mark_running(self) -> "SimulationRun":
        self._ensure_transition_allowed({SimulationStatus.SUBMITTED}, SimulationStatus.RUNNING)
        return self._validated_copy(status=SimulationStatus.RUNNING)

    def mark_succeeded(self, completed_at: datetime) -> "SimulationRun":
        self._ensure_transition_allowed(
            {SimulationStatus.SUBMITTED, SimulationStatus.RUNNING},
            SimulationStatus.SUCCEEDED,
        )
        return self._validated_copy(
            status=SimulationStatus.SUCCEEDED,
            completed_at=completed_at,
        )

    def mark_failed(self, completed_at: datetime) -> "SimulationRun":
        self._ensure_transition_allowed(
            {SimulationStatus.SUBMITTED, SimulationStatus.RUNNING},
            SimulationStatus.FAILED,
        )
        return self._validated_copy(
            status=SimulationStatus.FAILED,
            completed_at=completed_at,
        )

    def mark_timed_out(self, completed_at: datetime) -> "SimulationRun":
        self._ensure_transition_allowed(
            {SimulationStatus.SUBMITTED, SimulationStatus.RUNNING},
            SimulationStatus.TIMED_OUT,
        )
        return self._validated_copy(
            status=SimulationStatus.TIMED_OUT,
            completed_at=completed_at,
        )

    def _ensure_transition_allowed(
        self,
        allowed_current_statuses: set[SimulationStatus],
        next_status: SimulationStatus,
    ) -> None:
        if self.status not in allowed_current_statuses:
            allowed = ", ".join(status.value for status in sorted(allowed_current_statuses, key=lambda status: status.value))
            current_status = self.status.value if isinstance(self.status, SimulationStatus) else str(self.status)
            raise ValueError(
                f"cannot transition simulation run from {current_status} to {next_status.value}; "
                f"allowed current statuses: {allowed}"
            )

    def _validated_copy(self, **update: object) -> "SimulationRun":
        payload = self.model_dump(mode="python")
        payload.update(update)
        return type(self)(**payload)
