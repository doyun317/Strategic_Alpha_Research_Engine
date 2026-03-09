from datetime import datetime, timezone

from strategic_alpha_engine.application.services import RuleBasedRobustPromotionDecider, RuleBasedValidationRunner
from strategic_alpha_engine.application.workflows import (
    MultiPeriodValidateResult,
    MultiPeriodValidateWorkflow,
    RobustPromotionWorkflow,
    ValidateResult,
    ValidateWorkflow,
    ValidationOutcome,
    build_validation_matrix,
)
from strategic_alpha_engine.domain.enums import ValidationStage
from strategic_alpha_engine.domain.examples import (
    build_sample_expression_candidate,
    build_sample_hypothesis_spec,
    build_sample_signal_blueprint,
    build_sample_validation_record,
)


def test_robust_promotion_workflow_promotes_only_one_duplicate_signature():
    candidate_a = build_sample_expression_candidate().model_copy(
        update={"candidate_id": "cand.robust.001"}
    )
    candidate_b = build_sample_expression_candidate().model_copy(
        update={"candidate_id": "cand.robust.002"}
    )
    validate_result = MultiPeriodValidateWorkflow(
        validate_workflow=ValidateWorkflow(
            validation_runner=RuleBasedValidationRunner(
                base_time=datetime(2026, 1, 18, 10, 30, tzinfo=timezone.utc)
            )
        ),
        minimum_passing_periods=2,
    ).run(
        source_run_id="validate.quality_deterioration.101",
        candidate_source_run_id="simulate.quality_deterioration.101",
        hypothesis=build_sample_hypothesis_spec(),
        blueprint=build_sample_signal_blueprint(),
        candidates=[candidate_a, candidate_b],
        validation_stage=ValidationStage.STAGE_B,
        periods=["P1Y0M0D", "P3Y0M0D", "P5Y0M0D"],
    )

    result = RobustPromotionWorkflow(
        promotion_decider=RuleBasedRobustPromotionDecider()
    ).run(
        validate_result,
        candidates=[candidate_a, candidate_b],
    )

    assert result.promoted_candidate_ids == ["cand.robust.001"]
    assert result.held_candidate_ids == ["cand.robust.002"]
    assert result.rejected_candidate_ids == []
    assert result.outcomes[0].promotion.to_stage == "robust_candidate"
    assert "duplicate_expression_signature_with_robust_candidate" in result.outcomes[1].promotion.reasons


def test_robust_promotion_workflow_rejects_candidate_with_severe_validation_grade():
    candidate = build_sample_expression_candidate().model_copy(
        update={"candidate_id": "cand.robust.reject.001"}
    )
    hypothesis = build_sample_hypothesis_spec()
    blueprint = build_sample_signal_blueprint()
    validation_a = build_sample_validation_record().model_copy(
        update={
            "validation_id": "validation.validate.quality_deterioration.201.cand.robust.reject.001.stage_b.P1Y0M0D",
            "candidate_id": candidate.candidate_id,
            "source_run_id": "validate.quality_deterioration.201",
            "candidate_source_run_id": "simulate.quality_deterioration.201",
            "period": "P1Y0M0D",
            "grade": "D",
            "pass_decision": False,
            "reasons": ["validation_threshold_breach"],
        }
    )
    validation_b = build_sample_validation_record().model_copy(
        update={
            "validation_id": "validation.validate.quality_deterioration.201.cand.robust.reject.001.stage_b.P3Y0M0D",
            "candidate_id": candidate.candidate_id,
            "source_run_id": "validate.quality_deterioration.201",
            "candidate_source_run_id": "simulate.quality_deterioration.201",
            "period": "P3Y0M0D",
            "grade": "D",
            "pass_decision": False,
            "reasons": ["validation_threshold_breach"],
        }
    )
    period_result_a = ValidateResult(
        source_run_id="validate.quality_deterioration.201",
        candidate_source_run_id="simulate.quality_deterioration.201",
        hypothesis=hypothesis,
        blueprint=blueprint,
        outcomes=[ValidationOutcome(candidate=candidate, validation=validation_a)],
        validated_candidate_ids=[candidate.candidate_id],
        passed_candidate_ids=[],
        failed_candidate_ids=[candidate.candidate_id],
    )
    period_result_b = ValidateResult(
        source_run_id="validate.quality_deterioration.201",
        candidate_source_run_id="simulate.quality_deterioration.201",
        hypothesis=hypothesis,
        blueprint=blueprint,
        outcomes=[ValidationOutcome(candidate=candidate, validation=validation_b)],
        validated_candidate_ids=[candidate.candidate_id],
        passed_candidate_ids=[],
        failed_candidate_ids=[candidate.candidate_id],
    )
    matrix = build_validation_matrix(
        [validation_a, validation_b],
        source_run_id="validate.quality_deterioration.201",
        validation_stage=ValidationStage.STAGE_B,
        requested_periods=["P1Y0M0D", "P3Y0M0D"],
        minimum_passing_periods=1,
    )
    validate_result = MultiPeriodValidateResult(
        source_run_id="validate.quality_deterioration.201",
        candidate_source_run_id="simulate.quality_deterioration.201",
        hypothesis=hypothesis,
        blueprint=blueprint,
        validation_stage=ValidationStage.STAGE_B,
        requested_periods=["P1Y0M0D", "P3Y0M0D"],
        period_results=[period_result_a, period_result_b],
        validation_matrix=matrix,
        validated_candidate_ids=[candidate.candidate_id],
        passed_candidate_ids=[],
        failed_candidate_ids=[candidate.candidate_id],
    )

    result = RobustPromotionWorkflow(
        promotion_decider=RuleBasedRobustPromotionDecider()
    ).run(
        validate_result,
        candidates=[candidate],
    )

    assert result.promoted_candidate_ids == []
    assert result.held_candidate_ids == []
    assert result.rejected_candidate_ids == [candidate.candidate_id]
    assert result.outcomes[0].promotion.to_stage == "rejected"
    assert "failing_grade_d" in result.outcomes[0].promotion.reasons
