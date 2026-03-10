from __future__ import annotations

import re
from datetime import datetime

from pydantic import Field, field_validator, model_validator

from strategic_alpha_engine.domain.base import EngineModel
from strategic_alpha_engine.domain.common import IDENTIFIER_PATTERN, ensure_unique_sequence
from strategic_alpha_engine.domain.enums import (
    CandidateLifecycleStage,
    HumanReviewQueueStatus,
    ResearchFamily,
    RunKind,
    RunLifecycleStatus,
    ValidationBacklogStatus,
)

_TEST_PERIOD_PATTERN = re.compile(r"^P(?:\d+Y)?(?:\d+M)?(?:\d+D)?$")
_REVIEWER_PATTERN = r"^[A-Za-z0-9_.@-]{3,64}$"


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
    parent_run_id: str | None = Field(default=None, pattern=IDENTIFIER_PATTERN)
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
    simulation_candidate_count: int = Field(default=0, ge=0)
    simulation_success_count: int = Field(default=0, ge=0)
    simulation_failed_count: int = Field(default=0, ge=0)
    simulation_timed_out_count: int = Field(default=0, ge=0)
    stage_a_evaluation_count: int = Field(default=0, ge=0)
    stage_a_passed_count: int = Field(default=0, ge=0)
    median_stage_a_sharpe: float | None = None
    critique_pass_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    stage_a_pass_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    simulation_timeout_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    submission_ready_rate: float = Field(default=0.0, ge=0.0, le=1.0)
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
            self.simulation_candidate_count,
            self.stage_a_evaluation_count,
        )
        if any(count > self.total_candidates for count in compared_counts):
            raise ValueError("family stats counts must not exceed total_candidates")
        if self.simulation_success_count + self.simulation_failed_count + self.simulation_timed_out_count > self.simulation_candidate_count:
            raise ValueError("simulation outcome counts must not exceed simulation_candidate_count")
        if self.stage_a_passed_count > self.stage_a_evaluation_count:
            raise ValueError("stage_a_passed_count must not exceed stage_a_evaluation_count")
        return self


class FamilyLearnerSummary(EngineModel):
    family: ResearchFamily
    total_candidates: int = Field(ge=0)
    simulation_candidate_count: int = Field(ge=0)
    critique_pass_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    stage_a_pass_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    simulation_timeout_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    submission_ready_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    median_stage_a_sharpe: float | None = None
    latest_run_id: str | None = Field(default=None, pattern=IDENTIFIER_PATTERN)
    updated_at: datetime

    @field_validator("updated_at")
    @classmethod
    def validate_updated_at(cls, value: datetime) -> datetime:
        return _require_timezone_aware(value, "updated_at")


class AgendaQueueRecord(EngineModel):
    queue_record_id: str = Field(pattern=IDENTIFIER_PATTERN)
    source_run_id: str = Field(pattern=IDENTIFIER_PATTERN)
    iteration_index: int = Field(ge=1)
    rank: int = Field(ge=1)
    agenda_id: str = Field(pattern=IDENTIFIER_PATTERN)
    family: ResearchFamily
    agenda_name: str = Field(min_length=4, max_length=140)
    agenda_status: str = Field(pattern=r"^(active|paused|backlog|completed)$")
    base_priority: float = Field(ge=0.0, le=1.0)
    family_score: float = Field(ge=0.0, le=1.0)
    adjusted_priority: float = Field(ge=0.0, le=1.0)
    selected_for_execution: bool = False
    reasons: list[str] = Field(default_factory=list, max_length=16)
    recorded_at: datetime

    @field_validator("reasons")
    @classmethod
    def validate_reasons(cls, value: list[str]) -> list[str]:
        return ensure_unique_sequence(value, "reasons")

    @field_validator("recorded_at")
    @classmethod
    def validate_recorded_at(cls, value: datetime) -> datetime:
        return _require_timezone_aware(value, "recorded_at")


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


class SubmissionReadyCandidateRecord(EngineModel):
    inventory_record_id: str = Field(pattern=IDENTIFIER_PATTERN)
    candidate_id: str = Field(pattern=IDENTIFIER_PATTERN)
    hypothesis_id: str = Field(pattern=IDENTIFIER_PATTERN)
    blueprint_id: str = Field(pattern=IDENTIFIER_PATTERN)
    family: ResearchFamily
    source_run_id: str = Field(pattern=IDENTIFIER_PATTERN)
    robust_source_run_id: str = Field(pattern=IDENTIFIER_PATTERN)
    promotion_id: str = Field(pattern=IDENTIFIER_PATTERN)
    validation_ids: list[str] = Field(default_factory=list, max_length=32)
    requested_periods: list[str] = Field(default_factory=list, max_length=16)
    promoted_at: datetime
    notes: str | None = Field(default=None, max_length=240)

    @field_validator("validation_ids", "requested_periods")
    @classmethod
    def validate_unique_lists(cls, value: list[str], info) -> list[str]:
        validated = ensure_unique_sequence(value, info.field_name)
        if info.field_name == "requested_periods":
            for period in validated:
                if not _TEST_PERIOD_PATTERN.fullmatch(period) or not any(char.isdigit() for char in period):
                    raise ValueError("requested_periods must use ISO-8601 period shapes like P3Y0M0D")
        return validated

    @field_validator("promoted_at")
    @classmethod
    def validate_promoted_at(cls, value: datetime) -> datetime:
        return _require_timezone_aware(value, "promoted_at")


class HumanReviewQueueRecord(EngineModel):
    queue_record_id: str = Field(pattern=IDENTIFIER_PATTERN)
    queue_entry_id: str = Field(pattern=IDENTIFIER_PATTERN)
    inventory_record_id: str = Field(pattern=IDENTIFIER_PATTERN)
    candidate_id: str = Field(pattern=IDENTIFIER_PATTERN)
    hypothesis_id: str = Field(pattern=IDENTIFIER_PATTERN)
    blueprint_id: str = Field(pattern=IDENTIFIER_PATTERN)
    family: ResearchFamily
    submission_ready_source_run_id: str = Field(pattern=IDENTIFIER_PATTERN)
    status: HumanReviewQueueStatus = HumanReviewQueueStatus.PENDING
    source_run_id: str = Field(pattern=IDENTIFIER_PATTERN)
    priority: float = Field(default=0.8, ge=0.0, le=1.0)
    reviewer: str | None = Field(default=None, pattern=_REVIEWER_PATTERN)
    decision_id: str | None = Field(default=None, pattern=IDENTIFIER_PATTERN)
    created_at: datetime
    updated_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=240)

    @field_validator("created_at", "updated_at")
    @classmethod
    def validate_timestamps(cls, value: datetime | None, info) -> datetime | None:
        return _require_timezone_aware(value, info.field_name)

    @model_validator(mode="after")
    def validate_queue_state(self) -> "HumanReviewQueueRecord":
        if self.updated_at is not None and self.updated_at < self.created_at:
            raise ValueError("updated_at must be greater than or equal to created_at")
        if self.status == HumanReviewQueueStatus.PENDING:
            if self.reviewer is not None or self.decision_id is not None or self.updated_at is not None:
                raise ValueError("pending review queue records must not include reviewer, decision_id, or updated_at")
            return self
        if self.reviewer is None or self.decision_id is None or self.updated_at is None:
            raise ValueError("resolved review queue records must include reviewer, decision_id, and updated_at")
        return self
