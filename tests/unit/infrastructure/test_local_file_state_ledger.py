from datetime import datetime, timezone

from strategic_alpha_engine.application.contracts import (
    CandidateStageRecord,
    FamilyLearnerSummary,
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
from strategic_alpha_engine.infrastructure import LocalFileStateLedger


def test_local_file_state_ledger_appends_and_loads_state_manifests(tmp_path):
    ledger = LocalFileStateLedger(tmp_path / "artifacts")
    candidate_records = [
        CandidateStageRecord(
            stage_record_id="stage.quality_deterioration.001",
            candidate_id="cand.quality_deterioration.001",
            hypothesis_id="hyp.quality_deterioration.001",
            blueprint_id="bp.quality_deterioration.001",
            family="quality_deterioration",
            stage=CandidateLifecycleStage.CRITIQUE_PASSED,
            source_run_id="run.synthesize.001",
            recorded_at=datetime(2026, 1, 15, 15, 0, tzinfo=timezone.utc),
        ),
        CandidateStageRecord(
            stage_record_id="stage.quality_deterioration.002",
            candidate_id="cand.quality_deterioration.002",
            hypothesis_id="hyp.quality_deterioration.001",
            blueprint_id="bp.quality_deterioration.001",
            family="quality_deterioration",
            stage=CandidateLifecycleStage.REJECTED,
            source_run_id="run.synthesize.001",
            recorded_at=datetime(2026, 1, 15, 15, 1, tzinfo=timezone.utc),
        ),
    ]
    run_records = [
        RunStateRecord(
            run_id="run.simulate.001",
            run_kind=RunKind.SIMULATE,
            status=RunLifecycleStatus.COMPLETED,
            started_at=datetime(2026, 1, 15, 14, 30, tzinfo=timezone.utc),
            completed_at=datetime(2026, 1, 15, 14, 42, tzinfo=timezone.utc),
            candidate_count=4,
            accepted_candidate_count=4,
            simulated_candidate_count=4,
        )
    ]
    family_stats = [
        FamilyStatsSnapshot(
            family="quality_deterioration",
            total_candidates=4,
            critique_passed_candidates=4,
            sim_passed_candidates=4,
            robust_candidates=0,
            submission_ready_candidates=0,
            rejected_candidates=0,
            simulation_candidate_count=4,
            simulation_success_count=4,
            simulation_failed_count=0,
            simulation_timed_out_count=0,
            stage_a_evaluation_count=4,
            stage_a_passed_count=4,
            median_stage_a_sharpe=1.21,
            critique_pass_rate=1.0,
            stage_a_pass_rate=1.0,
            simulation_timeout_rate=0.0,
            submission_ready_rate=0.0,
            updated_at=datetime(2026, 1, 15, 15, 5, tzinfo=timezone.utc),
            last_run_id="run.simulate.001",
        )
    ]
    learner_summaries = [
        FamilyLearnerSummary(
            family="quality_deterioration",
            total_candidates=4,
            simulation_candidate_count=4,
            critique_pass_rate=1.0,
            stage_a_pass_rate=1.0,
            simulation_timeout_rate=0.0,
            submission_ready_rate=0.0,
            median_stage_a_sharpe=1.21,
            latest_run_id="run.simulate.001",
            updated_at=datetime(2026, 1, 15, 15, 5, tzinfo=timezone.utc),
        )
    ]
    backlog_entries = [
        ValidationBacklogEntry(
            backlog_entry_id="backlog.validation.001",
            candidate_id="cand.quality_deterioration.001",
            family="quality_deterioration",
            requested_period="P3Y0M0D",
            validation_stage="stage_b",
            priority=0.9,
            status=ValidationBacklogStatus.PENDING,
            source_run_id="run.simulate.001",
            created_at=datetime(2026, 1, 15, 15, 10, tzinfo=timezone.utc),
        )
    ]

    candidate_path = ledger.append_candidate_stage_records(candidate_records)
    run_path = ledger.append_run_state_records(run_records)
    family_path = ledger.write_family_stats(family_stats)
    learner_path = ledger.write_family_learner_summaries(learner_summaries)
    backlog_path = ledger.append_validation_backlog_entries(backlog_entries)

    assert candidate_path.name == "candidate_stages.jsonl"
    assert run_path.name == "run_states.jsonl"
    assert family_path.name == "family_stats.json"
    assert learner_path.name == "family_learner_summaries.json"
    assert backlog_path.name == "validation_backlog.jsonl"

    loaded_candidates = ledger.load_candidate_stage_records()
    loaded_runs = ledger.load_run_state_records()
    loaded_family_stats = ledger.load_family_stats()
    loaded_learner_summaries = ledger.load_family_learner_summaries()
    loaded_backlog = ledger.load_validation_backlog_entries()

    assert [record.stage for record in loaded_candidates] == [
        CandidateLifecycleStage.CRITIQUE_PASSED,
        CandidateLifecycleStage.REJECTED,
    ]
    assert loaded_runs[0].status == RunLifecycleStatus.COMPLETED
    assert loaded_family_stats[0].family == "quality_deterioration"
    assert loaded_family_stats[0].median_stage_a_sharpe == 1.21
    assert loaded_learner_summaries[0].stage_a_pass_rate == 1.0
    assert loaded_backlog[0].requested_period == "P3Y0M0D"


def test_local_file_state_ledger_returns_empty_lists_for_missing_manifests(tmp_path):
    ledger = LocalFileStateLedger(tmp_path / "artifacts")

    assert ledger.load_candidate_stage_records() == []
    assert ledger.load_run_state_records() == []
    assert ledger.load_family_stats() == []
    assert ledger.load_family_learner_summaries() == []
    assert ledger.load_validation_backlog_entries() == []
