from datetime import datetime, timezone

from strategic_alpha_engine.application.contracts import (
    AgendaQueueRecord,
    CandidateStageRecord,
    FamilyLearnerSummary,
    FamilyStatsSnapshot,
    HumanReviewQueueRecord,
    RunStateRecord,
    SubmissionReadyCandidateRecord,
    ValidationBacklogEntry,
)
from strategic_alpha_engine.domain.enums import (
    CandidateLifecycleStage,
    HumanReviewQueueStatus,
    RunKind,
    RunLifecycleStatus,
    ValidationBacklogStatus,
)
from strategic_alpha_engine.domain.review import HumanReviewDecision
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
    agenda_queue_records = [
        AgendaQueueRecord(
            queue_record_id="queue.research_loop.001.001",
            source_run_id="research_loop.quality_deterioration.001",
            iteration_index=1,
            rank=1,
            agenda_id="agenda.quality_deterioration.001",
            family="quality_deterioration",
            agenda_name="Quality deterioration queue",
            agenda_status="active",
            base_priority=0.8,
            family_score=0.7,
            adjusted_priority=0.74,
            selected_for_execution=True,
            reasons=["base_priority=0.8", "family_score=0.7"],
            recorded_at=datetime(2026, 1, 15, 15, 6, tzinfo=timezone.utc),
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
    submission_ready_records = [
        SubmissionReadyCandidateRecord(
            inventory_record_id="submission_ready.promote.001.cand.quality_deterioration.001",
            candidate_id="cand.quality_deterioration.001",
            hypothesis_id="hyp.quality_deterioration.001",
            blueprint_id="bp.quality_deterioration.001",
            family="quality_deterioration",
            source_run_id="promote.quality_deterioration.001",
            robust_source_run_id="validate.quality_deterioration.001",
            promotion_id="promotion.promote.quality_deterioration.001.cand.quality_deterioration.001.submission_ready",
            validation_ids=["validation.validate.quality_deterioration.001.cand.quality_deterioration.001.stage_b.P1Y0M0D"],
            requested_periods=["P1Y0M0D"],
            promoted_at=datetime(2026, 1, 15, 15, 11, tzinfo=timezone.utc),
        )
    ]
    human_review_queue_records = [
        HumanReviewQueueRecord(
            queue_record_id="review_queue.promote.quality_deterioration.001.cand.quality_deterioration.001.pending",
            queue_entry_id="review_queue.promote.quality_deterioration.001.cand.quality_deterioration.001",
            inventory_record_id="submission_ready.promote.quality_deterioration.001.cand.quality_deterioration.001",
            candidate_id="cand.quality_deterioration.001",
            hypothesis_id="hyp.quality_deterioration.001",
            blueprint_id="bp.quality_deterioration.001",
            family="quality_deterioration",
            submission_ready_source_run_id="promote.quality_deterioration.001",
            status=HumanReviewQueueStatus.PENDING,
            source_run_id="promote.quality_deterioration.001",
            created_at=datetime(2026, 1, 15, 15, 11, tzinfo=timezone.utc),
        )
    ]
    human_review_decisions = [
        HumanReviewDecision(
            decision_id="review.review.quality_deterioration.001.cand.quality_deterioration.001.approve",
            queue_entry_id="review_queue.promote.quality_deterioration.001.cand.quality_deterioration.001",
            candidate_id="cand.quality_deterioration.001",
            hypothesis_id="hyp.quality_deterioration.001",
            blueprint_id="bp.quality_deterioration.001",
            family="quality_deterioration",
            source_run_id="review.quality_deterioration.001",
            submission_ready_source_run_id="promote.quality_deterioration.001",
            decision="approve",
            to_stage="submission_ready",
            reviewer="reviewer_01",
            reasons=["manual_review_approved"],
            reviewed_at=datetime(2026, 1, 15, 15, 20, tzinfo=timezone.utc),
        )
    ]

    candidate_path = ledger.append_candidate_stage_records(candidate_records)
    run_path = ledger.append_run_state_records(run_records)
    agenda_queue_path = ledger.append_agenda_queue_records(agenda_queue_records)
    family_path = ledger.write_family_stats(family_stats)
    learner_path = ledger.write_family_learner_summaries(learner_summaries)
    backlog_path = ledger.append_validation_backlog_entries(backlog_entries)
    submission_ready_path = ledger.append_submission_ready_records(submission_ready_records)
    human_review_queue_path = ledger.append_human_review_queue_records(human_review_queue_records)
    human_review_decisions_path = ledger.append_human_review_decisions(human_review_decisions)

    assert candidate_path.name == "candidate_stages.jsonl"
    assert run_path.name == "run_states.jsonl"
    assert agenda_queue_path.name == "agenda_queue.jsonl"
    assert family_path.name == "family_stats.json"
    assert learner_path.name == "family_learner_summaries.json"
    assert backlog_path.name == "validation_backlog.jsonl"
    assert submission_ready_path.name == "submission_ready_candidates.jsonl"
    assert human_review_queue_path.name == "human_review_queue.jsonl"
    assert human_review_decisions_path.name == "human_review_decisions.jsonl"

    loaded_candidates = ledger.load_candidate_stage_records()
    loaded_runs = ledger.load_run_state_records()
    loaded_agenda_queue = ledger.load_agenda_queue_records()
    loaded_family_stats = ledger.load_family_stats()
    loaded_learner_summaries = ledger.load_family_learner_summaries()
    loaded_backlog = ledger.load_validation_backlog_entries()
    loaded_submission_ready = ledger.load_submission_ready_records()
    loaded_human_review_queue = ledger.load_human_review_queue_records()
    loaded_human_review_decisions = ledger.load_human_review_decisions()

    assert [record.stage for record in loaded_candidates] == [
        CandidateLifecycleStage.CRITIQUE_PASSED,
        CandidateLifecycleStage.REJECTED,
    ]
    assert loaded_runs[0].status == RunLifecycleStatus.COMPLETED
    assert loaded_agenda_queue[0].selected_for_execution is True
    assert loaded_family_stats[0].family == "quality_deterioration"
    assert loaded_family_stats[0].median_stage_a_sharpe == 1.21
    assert loaded_learner_summaries[0].stage_a_pass_rate == 1.0
    assert loaded_backlog[0].requested_period == "P3Y0M0D"
    assert loaded_submission_ready[0].source_run_id == "promote.quality_deterioration.001"
    assert loaded_human_review_queue[0].status == HumanReviewQueueStatus.PENDING
    assert loaded_human_review_decisions[0].decision == "approve"


def test_local_file_state_ledger_returns_empty_lists_for_missing_manifests(tmp_path):
    ledger = LocalFileStateLedger(tmp_path / "artifacts")

    assert ledger.load_candidate_stage_records() == []
    assert ledger.load_run_state_records() == []
    assert ledger.load_agenda_queue_records() == []
    assert ledger.load_family_stats() == []
    assert ledger.load_family_learner_summaries() == []
    assert ledger.load_validation_backlog_entries() == []
    assert ledger.load_submission_ready_records() == []
    assert ledger.load_human_review_queue_records() == []
    assert ledger.load_human_review_decisions() == []
