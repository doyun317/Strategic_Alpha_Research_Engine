from datetime import datetime, timezone

from strategic_alpha_engine.application.contracts import ValidationPromotionArtifactRecord
from strategic_alpha_engine.application.workflows import SubmissionReadyPromotionWorkflow
from strategic_alpha_engine.domain.enums import CandidateLifecycleStage, PromotionDecisionKind, ValidationStage
from strategic_alpha_engine.domain.examples import (
    build_sample_expression_candidate,
    build_sample_promotion_decision,
    build_sample_hypothesis_spec,
    build_sample_signal_blueprint,
)


def test_submission_ready_promotion_workflow_promotes_robust_candidates():
    candidate = build_sample_expression_candidate().model_copy(
        update={"candidate_id": "cand.submission_ready.001"}
    )
    robust_promotion = build_sample_promotion_decision().model_copy(
        update={
            "promotion_id": "promotion.validate.quality_deterioration.001.cand.submission_ready.001.stage_b.promote",
            "candidate_id": candidate.candidate_id,
            "source_run_id": "validate.quality_deterioration.001",
            "from_stage": CandidateLifecycleStage.SIM_PASSED,
            "to_stage": CandidateLifecycleStage.ROBUST_CANDIDATE,
            "decision": PromotionDecisionKind.PROMOTE,
            "reasons": ["validation_matrix_passed", "diversity_guard_cleared"],
        }
    )
    robust_record = ValidationPromotionArtifactRecord(
        candidate=candidate,
        validation_stage=ValidationStage.STAGE_B,
        requested_periods=["P1Y0M0D", "P3Y0M0D", "P5Y0M0D"],
        validation_ids=[
            "validation.validate.quality_deterioration.001.cand.submission_ready.001.stage_b.P1Y0M0D",
            "validation.validate.quality_deterioration.001.cand.submission_ready.001.stage_b.P3Y0M0D",
        ],
        passing_periods=["P1Y0M0D", "P3Y0M0D"],
        failing_periods=["P5Y0M0D"],
        aggregate_pass_decision=True,
        promotion=robust_promotion,
    )

    promoted_at = datetime(2026, 3, 9, 8, 45, tzinfo=timezone.utc)
    result = SubmissionReadyPromotionWorkflow().run(
        source_run_id="promote.quality_deterioration.001",
        robust_source_run_id="validate.quality_deterioration.001",
        hypothesis=build_sample_hypothesis_spec(),
        blueprint=build_sample_signal_blueprint(),
        robust_records=[robust_record],
        promoted_at=promoted_at,
    )

    assert result.promoted_candidate_ids == [candidate.candidate_id]
    assert result.outcomes[0].submission_promotion.to_stage == CandidateLifecycleStage.SUBMISSION_READY
    assert result.outcomes[0].submission_promotion.decided_at == promoted_at
    assert result.outcomes[0].submission_promotion.reasons == [
        "manual_promote_cli_invoked",
        "robust_candidate_confirmed",
    ]
