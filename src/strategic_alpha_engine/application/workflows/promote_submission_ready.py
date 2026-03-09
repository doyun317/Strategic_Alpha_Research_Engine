from __future__ import annotations

from datetime import datetime

from pydantic import Field

from strategic_alpha_engine.application.contracts import ValidationPromotionArtifactRecord
from strategic_alpha_engine.domain.base import EngineModel
from strategic_alpha_engine.domain.enums import CandidateLifecycleStage, PromotionDecisionKind
from strategic_alpha_engine.domain.hypothesis_spec import HypothesisSpec
from strategic_alpha_engine.domain.promotion import PromotionDecision
from strategic_alpha_engine.domain.signal_blueprint import SignalBlueprint


class SubmissionReadyPromotionOutcome(EngineModel):
    robust_promotion: ValidationPromotionArtifactRecord
    submission_promotion: PromotionDecision


class SubmissionReadyPromotionResult(EngineModel):
    source_run_id: str
    robust_source_run_id: str
    hypothesis: HypothesisSpec
    blueprint: SignalBlueprint
    outcomes: list[SubmissionReadyPromotionOutcome] = Field(default_factory=list)
    promoted_candidate_ids: list[str] = Field(default_factory=list)


class SubmissionReadyPromotionWorkflow:
    def run(
        self,
        *,
        source_run_id: str,
        robust_source_run_id: str,
        hypothesis: HypothesisSpec,
        blueprint: SignalBlueprint,
        robust_records: list[ValidationPromotionArtifactRecord],
        promoted_at: datetime,
    ) -> SubmissionReadyPromotionResult:
        if not robust_records:
            raise ValueError("robust_records must not be empty")

        outcomes: list[SubmissionReadyPromotionOutcome] = []
        promoted_candidate_ids: list[str] = []
        seen_candidate_ids: set[str] = set()

        for record in robust_records:
            candidate = record.candidate
            if candidate.candidate_id in seen_candidate_ids:
                raise ValueError("robust_records must not contain duplicate candidate_id values")
            seen_candidate_ids.add(candidate.candidate_id)
            if record.promotion.to_stage != CandidateLifecycleStage.ROBUST_CANDIDATE:
                raise ValueError("robust_records must only contain robust_candidate promotions")

            submission_promotion = PromotionDecision(
                promotion_id=f"promotion.{source_run_id}.{candidate.candidate_id}.submission_ready",
                candidate_id=candidate.candidate_id,
                hypothesis_id=candidate.hypothesis_id,
                blueprint_id=candidate.blueprint_id,
                evaluation_id=f"basis.{record.promotion.promotion_id}",
                source_run_id=source_run_id,
                from_stage=CandidateLifecycleStage.ROBUST_CANDIDATE,
                to_stage=CandidateLifecycleStage.SUBMISSION_READY,
                decision=PromotionDecisionKind.PROMOTE,
                reasons=[
                    "manual_promote_cli_invoked",
                    "robust_candidate_confirmed",
                ],
                decided_at=promoted_at,
            )
            outcomes.append(
                SubmissionReadyPromotionOutcome(
                    robust_promotion=record,
                    submission_promotion=submission_promotion,
                )
            )
            promoted_candidate_ids.append(candidate.candidate_id)

        return SubmissionReadyPromotionResult(
            source_run_id=source_run_id,
            robust_source_run_id=robust_source_run_id,
            hypothesis=hypothesis,
            blueprint=blueprint,
            outcomes=outcomes,
            promoted_candidate_ids=promoted_candidate_ids,
        )
