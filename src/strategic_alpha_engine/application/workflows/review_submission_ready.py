from __future__ import annotations

from datetime import datetime

from pydantic import Field

from strategic_alpha_engine.application.contracts import SubmissionReadyArtifactRecord
from strategic_alpha_engine.domain.base import EngineModel
from strategic_alpha_engine.domain.enums import (
    CandidateLifecycleStage,
    HumanReviewDecisionKind,
)
from strategic_alpha_engine.domain.hypothesis_spec import HypothesisSpec
from strategic_alpha_engine.domain.review import HumanReviewDecision
from strategic_alpha_engine.domain.signal_blueprint import SignalBlueprint


class HumanReviewOutcome(EngineModel):
    submission_ready: SubmissionReadyArtifactRecord
    review_decision: HumanReviewDecision


class HumanReviewResult(EngineModel):
    source_run_id: str
    submission_ready_source_run_id: str
    hypothesis: HypothesisSpec
    blueprint: SignalBlueprint
    reviewer: str
    decision: HumanReviewDecisionKind
    outcomes: list[HumanReviewOutcome] = Field(default_factory=list)
    reviewed_candidate_ids: list[str] = Field(default_factory=list)
    approved_candidate_ids: list[str] = Field(default_factory=list)
    held_candidate_ids: list[str] = Field(default_factory=list)
    rejected_candidate_ids: list[str] = Field(default_factory=list)


class HumanReviewWorkflow:
    def run(
        self,
        *,
        source_run_id: str,
        submission_ready_source_run_id: str,
        hypothesis: HypothesisSpec,
        blueprint: SignalBlueprint,
        submission_ready_records: list[SubmissionReadyArtifactRecord],
        reviewer: str,
        decision: HumanReviewDecisionKind,
        reviewed_at: datetime,
        notes: str | None = None,
    ) -> HumanReviewResult:
        if not submission_ready_records:
            raise ValueError("submission_ready_records must not be empty")

        stage_map = {
            HumanReviewDecisionKind.APPROVE: CandidateLifecycleStage.SUBMISSION_READY,
            HumanReviewDecisionKind.HOLD: CandidateLifecycleStage.ROBUST_CANDIDATE,
            HumanReviewDecisionKind.REJECT: CandidateLifecycleStage.REJECTED,
        }
        default_reasons = {
            HumanReviewDecisionKind.APPROVE: ["manual_review_approved", "submission_ready_confirmed"],
            HumanReviewDecisionKind.HOLD: ["manual_review_hold", "needs_follow_up_review"],
            HumanReviewDecisionKind.REJECT: ["manual_review_rejected", "submission_candidate_rejected"],
        }

        outcomes: list[HumanReviewOutcome] = []
        reviewed_candidate_ids: list[str] = []
        approved_candidate_ids: list[str] = []
        held_candidate_ids: list[str] = []
        rejected_candidate_ids: list[str] = []
        seen_candidate_ids: set[str] = set()

        for record in submission_ready_records:
            candidate = record.candidate
            if candidate.candidate_id in seen_candidate_ids:
                raise ValueError("submission_ready_records must not contain duplicate candidate_id values")
            seen_candidate_ids.add(candidate.candidate_id)

            review_decision = HumanReviewDecision(
                decision_id=f"review.{source_run_id}.{candidate.candidate_id}.{decision.value}",
                queue_entry_id=f"review_queue.{submission_ready_source_run_id}.{candidate.candidate_id}",
                candidate_id=candidate.candidate_id,
                hypothesis_id=candidate.hypothesis_id,
                blueprint_id=candidate.blueprint_id,
                family=hypothesis.family,
                source_run_id=source_run_id,
                submission_ready_source_run_id=submission_ready_source_run_id,
                decision=decision,
                to_stage=stage_map[decision],
                reviewer=reviewer,
                reasons=default_reasons[decision],
                notes=notes,
                reviewed_at=reviewed_at,
            )
            outcomes.append(
                HumanReviewOutcome(
                    submission_ready=record,
                    review_decision=review_decision,
                )
            )
            reviewed_candidate_ids.append(candidate.candidate_id)
            if decision == HumanReviewDecisionKind.APPROVE:
                approved_candidate_ids.append(candidate.candidate_id)
            elif decision == HumanReviewDecisionKind.HOLD:
                held_candidate_ids.append(candidate.candidate_id)
            else:
                rejected_candidate_ids.append(candidate.candidate_id)

        return HumanReviewResult(
            source_run_id=source_run_id,
            submission_ready_source_run_id=submission_ready_source_run_id,
            hypothesis=hypothesis,
            blueprint=blueprint,
            reviewer=reviewer,
            decision=decision,
            outcomes=outcomes,
            reviewed_candidate_ids=reviewed_candidate_ids,
            approved_candidate_ids=approved_candidate_ids,
            held_candidate_ids=held_candidate_ids,
            rejected_candidate_ids=rejected_candidate_ids,
        )
