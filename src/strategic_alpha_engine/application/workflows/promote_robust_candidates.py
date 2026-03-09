from __future__ import annotations

from collections import defaultdict

from pydantic import Field

from strategic_alpha_engine.application.services.rule_based_robust_promotion import (
    RuleBasedRobustPromotionDecider,
    candidate_signature,
)
from strategic_alpha_engine.application.workflows.validate import MultiPeriodValidateResult
from strategic_alpha_engine.domain.base import EngineModel
from strategic_alpha_engine.domain.expression_candidate import ExpressionCandidate
from strategic_alpha_engine.domain.hypothesis_spec import HypothesisSpec
from strategic_alpha_engine.domain.promotion import PromotionDecision
from strategic_alpha_engine.domain.signal_blueprint import SignalBlueprint
from strategic_alpha_engine.domain.validation import ValidationRecord


class RobustPromotionOutcome(EngineModel):
    candidate: ExpressionCandidate
    validation_records: list[ValidationRecord] = Field(default_factory=list)
    requested_periods: list[str] = Field(default_factory=list)
    passing_periods: list[str] = Field(default_factory=list)
    failing_periods: list[str] = Field(default_factory=list)
    aggregate_pass_decision: bool
    signature: str
    promotion: PromotionDecision


class RobustPromotionResult(EngineModel):
    source_run_id: str
    candidate_source_run_id: str
    hypothesis: HypothesisSpec
    blueprint: SignalBlueprint
    validation_stage: str
    requested_periods: list[str] = Field(default_factory=list)
    outcomes: list[RobustPromotionOutcome] = Field(default_factory=list)
    promoted_candidate_ids: list[str] = Field(default_factory=list)
    held_candidate_ids: list[str] = Field(default_factory=list)
    rejected_candidate_ids: list[str] = Field(default_factory=list)


class RobustPromotionWorkflow:
    def __init__(self, promotion_decider: RuleBasedRobustPromotionDecider):
        self.promotion_decider = promotion_decider

    def run(
        self,
        validation_result: MultiPeriodValidateResult,
        *,
        candidates: list[ExpressionCandidate],
        existing_robust_signature_counts: dict[str, int] | None = None,
    ) -> RobustPromotionResult:
        candidate_by_id = {
            candidate.candidate_id: candidate
            for candidate in candidates
        }
        if len(candidate_by_id) != len(candidates):
            raise ValueError("candidates must not contain duplicate candidate_id values")

        validation_records_by_candidate: dict[str, list[ValidationRecord]] = defaultdict(list)
        for period_result in validation_result.period_results:
            for outcome in period_result.outcomes:
                validation_records_by_candidate[outcome.candidate.candidate_id].append(outcome.validation)

        signature_counts = dict(existing_robust_signature_counts or {})
        outcomes: list[RobustPromotionOutcome] = []
        promoted_candidate_ids: list[str] = []
        held_candidate_ids: list[str] = []
        rejected_candidate_ids: list[str] = []

        for row in validation_result.validation_matrix.rows:
            candidate = candidate_by_id.get(row.candidate_id)
            if candidate is None:
                raise ValueError("validation matrix contains a candidate_id that is missing from candidates")

            validation_records = sorted(
                validation_records_by_candidate.get(row.candidate_id, []),
                key=lambda record: record.period,
            )
            if not validation_records:
                raise ValueError("validation matrix row is missing supporting validation records")

            signature = candidate_signature(candidate)
            promotion = self.promotion_decider.decide(
                candidate,
                validation_records,
                source_run_id=validation_result.source_run_id,
                validation_stage=validation_result.validation_stage,
                aggregate_pass_decision=row.aggregate_pass_decision,
                aggregate_reasons=row.reasons,
                signature_collision_count=signature_counts.get(signature, 0),
            )
            if promotion.to_stage == "robust_candidate":
                signature_counts[signature] = signature_counts.get(signature, 0) + 1
                promoted_candidate_ids.append(candidate.candidate_id)
            elif promotion.to_stage == "rejected":
                rejected_candidate_ids.append(candidate.candidate_id)
            else:
                held_candidate_ids.append(candidate.candidate_id)

            outcomes.append(
                RobustPromotionOutcome(
                    candidate=candidate,
                    validation_records=validation_records,
                    requested_periods=validation_result.requested_periods,
                    passing_periods=row.passing_periods,
                    failing_periods=row.failing_periods,
                    aggregate_pass_decision=row.aggregate_pass_decision,
                    signature=signature,
                    promotion=promotion,
                )
            )

        return RobustPromotionResult(
            source_run_id=validation_result.source_run_id,
            candidate_source_run_id=validation_result.candidate_source_run_id,
            hypothesis=validation_result.hypothesis,
            blueprint=validation_result.blueprint,
            validation_stage=validation_result.validation_stage,
            requested_periods=validation_result.requested_periods,
            outcomes=outcomes,
            promoted_candidate_ids=promoted_candidate_ids,
            held_candidate_ids=held_candidate_ids,
            rejected_candidate_ids=rejected_candidate_ids,
        )
