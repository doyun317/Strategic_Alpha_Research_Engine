from __future__ import annotations

from datetime import datetime

from pydantic import Field

from strategic_alpha_engine.application.contracts import (
    CandidateArtifactRecord,
    EvaluationArtifactRecord,
    PromotionArtifactRecord,
    SimulationArtifactRecord,
    SubmissionPacketArtifactRecord,
    SubmissionPacketValidationSummary,
    SubmissionReadyArtifactRecord,
)
from strategic_alpha_engine.domain.base import EngineModel
from strategic_alpha_engine.domain.common import ensure_unique_sequence
from strategic_alpha_engine.domain.hypothesis_spec import HypothesisSpec
from strategic_alpha_engine.domain.research_agenda import ResearchAgenda
from strategic_alpha_engine.domain.review import HumanReviewDecision
from strategic_alpha_engine.domain.signal_blueprint import SignalBlueprint
from strategic_alpha_engine.domain.validation import ValidationRecord


class SubmissionPacketBundle(EngineModel):
    candidate_artifact: CandidateArtifactRecord
    simulation_artifact: SimulationArtifactRecord
    evaluation_artifact: EvaluationArtifactRecord
    stage_a_promotion: PromotionArtifactRecord
    submission_ready: SubmissionReadyArtifactRecord
    validation_records: list[ValidationRecord] = Field(default_factory=list)
    review_decision: HumanReviewDecision


class SubmissionPacketResult(EngineModel):
    source_run_id: str
    review_source_run_id: str
    agenda: ResearchAgenda | None = None
    hypothesis: HypothesisSpec
    blueprint: SignalBlueprint
    packets: list[SubmissionPacketArtifactRecord] = Field(default_factory=list)
    candidate_ids: list[str] = Field(default_factory=list)


class SubmissionPacketWorkflow:
    def run(
        self,
        *,
        source_run_id: str,
        review_source_run_id: str,
        agenda: ResearchAgenda | None,
        hypothesis: HypothesisSpec,
        blueprint: SignalBlueprint,
        bundles: list[SubmissionPacketBundle],
        generated_at: datetime,
    ) -> SubmissionPacketResult:
        if not bundles:
            raise ValueError("bundles must not be empty")

        packets: list[SubmissionPacketArtifactRecord] = []
        candidate_ids: list[str] = []
        seen_candidate_ids: set[str] = set()

        for bundle in bundles:
            candidate_id = bundle.candidate_artifact.candidate.candidate_id
            if candidate_id in seen_candidate_ids:
                raise ValueError("bundles must not contain duplicate candidate_id values")
            seen_candidate_ids.add(candidate_id)
            if not bundle.validation_records:
                raise ValueError("submission packet bundles must include validation_records")

            validation_ids = [record.validation_id for record in bundle.validation_records]
            ensure_unique_sequence(validation_ids, "validation_ids")
            requested_periods = list(bundle.submission_ready.robust_promotion.requested_periods)
            grades_by_period = {
                record.period: record.grade
                for record in bundle.validation_records
            }
            checks: list[str] = []
            reasons: list[str] = []
            for record in bundle.validation_records:
                for check in record.checks:
                    if check not in checks:
                        checks.append(check)
                for reason in record.reasons:
                    if reason not in reasons:
                        reasons.append(reason)

            validation_summary = SubmissionPacketValidationSummary(
                validation_stage=bundle.submission_ready.robust_promotion.validation_stage,
                validation_source_run_id=bundle.submission_ready.robust_promotion.promotion.source_run_id,
                candidate_source_run_id=bundle.validation_records[0].candidate_source_run_id,
                requested_periods=requested_periods,
                validation_ids=validation_ids,
                passing_periods=bundle.submission_ready.robust_promotion.passing_periods,
                failing_periods=bundle.submission_ready.robust_promotion.failing_periods,
                grades_by_period=grades_by_period,
                aggregate_pass_decision=bundle.submission_ready.robust_promotion.aggregate_pass_decision,
                checks=checks,
                reasons=reasons,
            )
            packets.append(
                SubmissionPacketArtifactRecord(
                    packet_id=f"packet.{source_run_id}.{candidate_id}",
                    source_run_id=source_run_id,
                    review_source_run_id=review_source_run_id,
                    submission_ready_source_run_id=bundle.submission_ready.submission_promotion.source_run_id,
                    generated_at=generated_at,
                    agenda=agenda,
                    hypothesis=hypothesis,
                    blueprint=blueprint,
                    candidate_artifact=bundle.candidate_artifact,
                    simulation_artifact=bundle.simulation_artifact,
                    evaluation_artifact=bundle.evaluation_artifact,
                    stage_a_promotion=bundle.stage_a_promotion,
                    submission_ready=bundle.submission_ready,
                    validation_summary=validation_summary,
                    validation_records=bundle.validation_records,
                    review_decision=bundle.review_decision,
                )
            )
            candidate_ids.append(candidate_id)

        return SubmissionPacketResult(
            source_run_id=source_run_id,
            review_source_run_id=review_source_run_id,
            agenda=agenda,
            hypothesis=hypothesis,
            blueprint=blueprint,
            packets=packets,
            candidate_ids=candidate_ids,
        )
