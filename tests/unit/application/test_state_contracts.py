from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from strategic_alpha_engine.application.contracts import (
    CandidateStageRecord,
    FamilyStatsSnapshot,
    RunStateRecord,
    ValidationBacklogEntry,
)
from strategic_alpha_engine.domain.enums import (
    CandidateLifecycleStage,
    RunKind,
    RunLifecycleStatus,
    ValidationBacklogStatus,
)


def test_run_state_record_rejects_failed_without_error_message():
    with pytest.raises(ValidationError, match="failed run state records must include error_message"):
        RunStateRecord(
            run_id="run.simulate.001",
            run_kind=RunKind.SIMULATE,
            status=RunLifecycleStatus.FAILED,
            started_at=datetime(2026, 1, 15, 14, 30, tzinfo=timezone.utc),
            completed_at=datetime(2026, 1, 15, 14, 42, tzinfo=timezone.utc),
        )


def test_family_stats_snapshot_rejects_counts_above_total():
    with pytest.raises(ValidationError, match="must not exceed total_candidates"):
        FamilyStatsSnapshot(
            family="quality_deterioration",
            total_candidates=2,
            critique_passed_candidates=3,
            sim_passed_candidates=1,
            robust_candidates=0,
            submission_ready_candidates=0,
            rejected_candidates=0,
            updated_at=datetime(2026, 1, 15, 15, 0, tzinfo=timezone.utc),
        )


def test_validation_backlog_entry_rejects_invalid_period_shape():
    with pytest.raises(ValidationError, match="requested_period must use an ISO-8601 period shape like P3Y0M0D"):
        ValidationBacklogEntry(
            backlog_entry_id="backlog.validation.001",
            candidate_id="cand.quality_deterioration.001",
            family="quality_deterioration",
            requested_period="3Y",
            validation_stage="stage_b",
            priority=0.8,
            status=ValidationBacklogStatus.PENDING,
            source_run_id="run.simulate.001",
            created_at=datetime(2026, 1, 15, 15, 0, tzinfo=timezone.utc),
        )


def test_candidate_stage_record_accepts_timezone_aware_timestamp():
    record = CandidateStageRecord(
        stage_record_id="stage.quality_deterioration.001",
        candidate_id="cand.quality_deterioration.001",
        hypothesis_id="hyp.quality_deterioration.001",
        blueprint_id="bp.quality_deterioration.001",
        family="quality_deterioration",
        stage=CandidateLifecycleStage.CRITIQUE_PASSED,
        source_run_id="run.synthesize.001",
        recorded_at=datetime(2026, 1, 15, 15, 0, tzinfo=timezone.utc),
    )

    assert record.stage == CandidateLifecycleStage.CRITIQUE_PASSED
