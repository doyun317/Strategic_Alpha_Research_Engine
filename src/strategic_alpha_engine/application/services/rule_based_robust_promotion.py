from __future__ import annotations

from pydantic import Field

from strategic_alpha_engine.domain.base import EngineModel
from strategic_alpha_engine.domain.enums import CandidateLifecycleStage, PromotionDecisionKind
from strategic_alpha_engine.domain.expression_candidate import ExpressionCandidate
from strategic_alpha_engine.domain.promotion import PromotionDecision
from strategic_alpha_engine.domain.validation import ValidationRecord


def candidate_signature(candidate: ExpressionCandidate) -> str:
    skeleton = candidate.skeleton_template_id or "manual"
    return f"{skeleton}::{candidate.normalized_expression}"


class RobustPromotionThresholds(EngineModel):
    max_robust_per_signature: int = Field(default=1, ge=1, le=10)


class RuleBasedRobustPromotionDecider:
    def __init__(self, thresholds: RobustPromotionThresholds | None = None):
        self.thresholds = thresholds or RobustPromotionThresholds()

    def decide(
        self,
        candidate: ExpressionCandidate,
        validation_records: list[ValidationRecord],
        *,
        source_run_id: str,
        validation_stage: str,
        aggregate_pass_decision: bool,
        aggregate_reasons: list[str],
        signature_collision_count: int,
    ) -> PromotionDecision:
        if not validation_records:
            raise ValueError("validation_records must not be empty")

        failing_grades = {
            record.grade.upper()
            for record in validation_records
            if record.grade
        } & {"D", "F"}
        all_checks = {
            check.lower()
            for record in validation_records
            for check in record.checks
        }
        severe_failure = bool(failing_grades) or any(
            check.startswith("fatal_") or check.startswith("hard_fail")
            for check in all_checks
        )
        decided_at = max(record.validated_at for record in validation_records)
        evaluation_id = f"validation.aggregate.{source_run_id}.{candidate.candidate_id}"

        if severe_failure:
            reasons = sorted(
                {f"failing_grade_{grade.lower()}" for grade in failing_grades}
                | {
                    check
                    for check in all_checks
                    if check.startswith("fatal_") or check.startswith("hard_fail")
                }
            ) or ["severe_validation_failure"]
            return PromotionDecision(
                promotion_id=f"promotion.{source_run_id}.{candidate.candidate_id}.{validation_stage}.reject",
                candidate_id=candidate.candidate_id,
                hypothesis_id=candidate.hypothesis_id,
                blueprint_id=candidate.blueprint_id,
                evaluation_id=evaluation_id,
                source_run_id=source_run_id,
                from_stage=CandidateLifecycleStage.SIM_PASSED,
                to_stage=CandidateLifecycleStage.REJECTED,
                decision=PromotionDecisionKind.REJECT,
                reasons=reasons,
                decided_at=decided_at,
            )

        if not aggregate_pass_decision:
            return PromotionDecision(
                promotion_id=f"promotion.{source_run_id}.{candidate.candidate_id}.{validation_stage}.hold",
                candidate_id=candidate.candidate_id,
                hypothesis_id=candidate.hypothesis_id,
                blueprint_id=candidate.blueprint_id,
                evaluation_id=evaluation_id,
                source_run_id=source_run_id,
                from_stage=CandidateLifecycleStage.SIM_PASSED,
                to_stage=CandidateLifecycleStage.SIM_PASSED,
                decision=PromotionDecisionKind.HOLD,
                reasons=["validation_matrix_not_passed", *aggregate_reasons][:16],
                decided_at=decided_at,
            )

        if signature_collision_count >= self.thresholds.max_robust_per_signature:
            return PromotionDecision(
                promotion_id=f"promotion.{source_run_id}.{candidate.candidate_id}.{validation_stage}.hold",
                candidate_id=candidate.candidate_id,
                hypothesis_id=candidate.hypothesis_id,
                blueprint_id=candidate.blueprint_id,
                evaluation_id=evaluation_id,
                source_run_id=source_run_id,
                from_stage=CandidateLifecycleStage.SIM_PASSED,
                to_stage=CandidateLifecycleStage.SIM_PASSED,
                decision=PromotionDecisionKind.HOLD,
                reasons=["duplicate_expression_signature_with_robust_candidate", *aggregate_reasons][:16],
                decided_at=decided_at,
            )

        return PromotionDecision(
            promotion_id=f"promotion.{source_run_id}.{candidate.candidate_id}.{validation_stage}.promote",
            candidate_id=candidate.candidate_id,
            hypothesis_id=candidate.hypothesis_id,
            blueprint_id=candidate.blueprint_id,
            evaluation_id=evaluation_id,
            source_run_id=source_run_id,
            from_stage=CandidateLifecycleStage.SIM_PASSED,
            to_stage=CandidateLifecycleStage.ROBUST_CANDIDATE,
            decision=PromotionDecisionKind.PROMOTE,
            reasons=["validation_matrix_passed", "diversity_guard_cleared", *aggregate_reasons][:16],
            decided_at=decided_at,
        )
