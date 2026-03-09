from __future__ import annotations

import re
from datetime import datetime

from pydantic import Field, field_validator, model_validator

from strategic_alpha_engine.domain.base import EngineModel
from strategic_alpha_engine.domain.common import IDENTIFIER_PATTERN
from strategic_alpha_engine.domain.enums import (
    CandidateLifecycleStage,
    ResearchFamily,
    RunKind,
    RunLifecycleStatus,
    ValidationBacklogStatus,
)

_TEST_PERIOD_PATTERN = re.compile(r"^P(?:\d+Y)?(?:\d+M)?(?:\d+D)?$")


def _require_timezone_aware(value: datetime | None, field_name: str) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


class CandidateStageRecord(EngineModel):
    stage_record_id: str = Field(pattern=IDENTIFIER_PATTERN)
    candidate_id: str = Field(pattern=IDENTIFIER_PATTERN)
    hypothesis_id: str = Field(pattern=IDENTIFIER_PATTERN)
    blueprint_id: str = Field(pattern=IDENTIFIER_PATTERN)
    family: ResearchFamily
    stage: CandidateLifecycleStage
    source_run_id: str = Field(pattern=IDENTIFIER_PATTERN)
    recorded_at: datetime
    notes: str | None = Field(default=None, max_length=240)

    @field_validator("recorded_at")
    @classmethod
    def validate_recorded_at(cls, value: datetime) -> datetime:
        return _require_timezone_aware(value, "recorded_at")


class RunStateRecord(EngineModel):
    run_id: str = Field(pattern=IDENTIFIER_PATTERN)
    run_kind: RunKind
    status: RunLifecycleStatus
    started_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = Field(default=None, max_length=300)
    candidate_count: int | None = Field(default=None, ge=0)
    accepted_candidate_count: int | None = Field(default=None, ge=0)
    simulated_candidate_count: int | None = Field(default=None, ge=0)

    @field_validator("started_at", "completed_at")
    @classmethod
    def validate_timestamps(cls, value: datetime | None, info) -> datetime | None:
        return _require_timezone_aware(value, info.field_name)

    @model_validator(mode="after")
    def validate_status_shape(self) -> "RunStateRecord":
        if self.status == RunLifecycleStatus.STARTED:
            if self.completed_at is not None or self.error_message is not None:
                raise ValueError("started run state records must not include completed_at or error_message")
            return self

        if self.completed_at is None:
            raise ValueError("completed or failed run state records must include completed_at")
        if self.completed_at < self.started_at:
            raise ValueError("completed_at must be greater than or equal to started_at")
        if self.status == RunLifecycleStatus.COMPLETED and self.error_message is not None:
            raise ValueError("completed run state records must not include error_message")
        if self.status == RunLifecycleStatus.FAILED and not self.error_message:
            raise ValueError("failed run state records must include error_message")
        return self


class FamilyStatsSnapshot(EngineModel):
    family: ResearchFamily
    total_candidates: int = Field(ge=0)
    critique_passed_candidates: int = Field(ge=0)
    sim_passed_candidates: int = Field(ge=0)
    robust_candidates: int = Field(ge=0)
    submission_ready_candidates: int = Field(ge=0)
    rejected_candidates: int = Field(ge=0)
    updated_at: datetime
    last_run_id: str | None = Field(default=None, pattern=IDENTIFIER_PATTERN)

    @field_validator("updated_at")
    @classmethod
    def validate_updated_at(cls, value: datetime) -> datetime:
        return _require_timezone_aware(value, "updated_at")

    @model_validator(mode="after")
    def validate_candidate_counts(self) -> "FamilyStatsSnapshot":
        compared_counts = (
            self.critique_passed_candidates,
            self.sim_passed_candidates,
            self.robust_candidates,
            self.submission_ready_candidates,
            self.rejected_candidates,
        )
        if any(count > self.total_candidates for count in compared_counts):
            raise ValueError("family stats counts must not exceed total_candidates")
        return self


class ValidationBacklogEntry(EngineModel):
    backlog_entry_id: str = Field(pattern=IDENTIFIER_PATTERN)
    candidate_id: str = Field(pattern=IDENTIFIER_PATTERN)
    family: ResearchFamily
    requested_period: str = Field(min_length=2, max_length=32)
    validation_stage: str = Field(pattern=r"^stage_[a-z0-9_]+$")
    priority: float = Field(default=0.5, ge=0.0, le=1.0)
    status: ValidationBacklogStatus = ValidationBacklogStatus.PENDING
    source_run_id: str = Field(pattern=IDENTIFIER_PATTERN)
    created_at: datetime
    updated_at: datetime | None = None

    @field_validator("requested_period")
    @classmethod
    def validate_requested_period(cls, value: str) -> str:
        if not _TEST_PERIOD_PATTERN.fullmatch(value) or not any(char.isdigit() for char in value):
            raise ValueError("requested_period must use an ISO-8601 period shape like P3Y0M0D")
        return value

    @field_validator("created_at", "updated_at")
    @classmethod
    def validate_timestamps(cls, value: datetime | None, info) -> datetime | None:
        return _require_timezone_aware(value, info.field_name)

    @model_validator(mode="after")
    def validate_timeline(self) -> "ValidationBacklogEntry":
        if self.updated_at is not None and self.updated_at < self.created_at:
            raise ValueError("updated_at must be greater than or equal to created_at")
        return self
