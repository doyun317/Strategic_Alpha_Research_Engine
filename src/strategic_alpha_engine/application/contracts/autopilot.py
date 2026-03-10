from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator

from strategic_alpha_engine.domain.base import EngineModel
from strategic_alpha_engine.domain.common import IDENTIFIER_PATTERN, ensure_unique_sequence
from strategic_alpha_engine.domain.enums import AutopilotStopReason, ResearchFamily


def _require_timezone_aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


class AutopilotIterationRecord(EngineModel):
    iteration_record_id: str = Field(pattern=IDENTIFIER_PATTERN)
    autopilot_run_id: str = Field(pattern=IDENTIFIER_PATTERN)
    iteration_index: int = Field(ge=1)
    agenda_id: str = Field(pattern=IDENTIFIER_PATTERN)
    agenda_name: str = Field(min_length=4, max_length=140)
    family: ResearchFamily
    simulate_run_id: str = Field(pattern=IDENTIFIER_PATTERN)
    validate_run_id: str | None = Field(default=None, pattern=IDENTIFIER_PATTERN)
    promoted_candidate_ids: list[str] = Field(default_factory=list, max_length=64)
    held_candidate_ids: list[str] = Field(default_factory=list, max_length=64)
    rejected_candidate_ids: list[str] = Field(default_factory=list, max_length=64)
    manifest_candidate_ids: list[str] = Field(default_factory=list, max_length=64)
    queue_depth_after_iteration: int = Field(ge=0)
    recorded_at: datetime

    @field_validator(
        "promoted_candidate_ids",
        "held_candidate_ids",
        "rejected_candidate_ids",
        "manifest_candidate_ids",
    )
    @classmethod
    def validate_unique_lists(cls, value: list[str], info) -> list[str]:
        return ensure_unique_sequence(value, info.field_name)

    @field_validator("recorded_at")
    @classmethod
    def validate_recorded_at(cls, value: datetime) -> datetime:
        return _require_timezone_aware(value, "recorded_at")


class SubmissionPacketIndexRecord(EngineModel):
    index_entry_id: str = Field(pattern=IDENTIFIER_PATTERN)
    autopilot_run_id: str = Field(pattern=IDENTIFIER_PATTERN)
    packet_run_id: str = Field(pattern=IDENTIFIER_PATTERN)
    candidate_id: str = Field(pattern=IDENTIFIER_PATTERN)
    family: ResearchFamily
    signature: str = Field(min_length=4, max_length=640)
    packet_id: str = Field(pattern=IDENTIFIER_PATTERN)
    packet_path: str = Field(min_length=8, max_length=1000)
    source_run_ids: list[str] = Field(default_factory=list, max_length=32)
    passing_period_count: int = Field(default=0, ge=0, le=32)
    stage_a_sharpe: float | None = None
    fitness: float | None = None
    turnover: float | None = None
    recorded_at: datetime

    @field_validator("source_run_ids")
    @classmethod
    def validate_source_run_ids(cls, value: list[str]) -> list[str]:
        return ensure_unique_sequence(value, "source_run_ids")

    @field_validator("recorded_at")
    @classmethod
    def validate_recorded_at(cls, value: datetime) -> datetime:
        return _require_timezone_aware(value, "recorded_at")


class AutopilotManifest(EngineModel):
    autopilot_run_id: str = Field(pattern=IDENTIFIER_PATTERN)
    generated_at: datetime
    stopped_reason: AutopilotStopReason
    target_packet_count: int = Field(ge=0)
    selected_packet_count: int = Field(ge=0)
    candidate_ids: list[str] = Field(default_factory=list, max_length=256)
    packet_ids: list[str] = Field(default_factory=list, max_length=256)
    packet_paths: list[str] = Field(default_factory=list, max_length=256)
    review_mode: str = Field(default="synthetic_auto_approve", min_length=4, max_length=120)
    selection_policy: str = Field(min_length=8, max_length=300)
    source_run_ids: list[str] = Field(default_factory=list, max_length=256)

    @field_validator("candidate_ids", "packet_ids", "packet_paths", "source_run_ids")
    @classmethod
    def validate_unique_lists(cls, value: list[str], info) -> list[str]:
        return ensure_unique_sequence(value, info.field_name)

    @field_validator("generated_at")
    @classmethod
    def validate_generated_at(cls, value: datetime) -> datetime:
        return _require_timezone_aware(value, "generated_at")
