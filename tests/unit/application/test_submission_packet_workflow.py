from datetime import datetime, timezone

from strategic_alpha_engine.application.services import (
    RuleBasedRobustPromotionDecider,
    RuleBasedStageAEvaluator,
    RuleBasedStageAPromotionDecider,
    RuleBasedValidationRunner,
)
from strategic_alpha_engine.application.workflows import (
    HumanReviewWorkflow,
    MultiPeriodValidateWorkflow,
    RobustPromotionWorkflow,
    SimulationExecutionPolicy,
    SimulationOrchestratorWorkflow,
    StageAEvaluationWorkflow,
    SubmissionPacketBundle,
    SubmissionPacketWorkflow,
    SubmissionReadyPromotionWorkflow,
    ValidateWorkflow,
)
from strategic_alpha_engine.domain.enums import HumanReviewDecisionKind, ValidationStage
from strategic_alpha_engine.infrastructure import FakeBrainSimulationClient, LocalFileArtifactLedger
from strategic_alpha_engine.testing import build_sample_plan_result, build_sample_synthesize_result


def test_submission_packet_workflow_builds_self_contained_packet():
    plan_result = build_sample_plan_result()
    synthesize_result = build_sample_synthesize_result(plan_result)
    simulation_result = SimulationOrchestratorWorkflow(
        brain_client=FakeBrainSimulationClient(),
        max_polls=3,
    ).run(
        synthesize_result=synthesize_result,
        policy=SimulationExecutionPolicy(),
    )
    stage_a_result = StageAEvaluationWorkflow(
        evaluator=RuleBasedStageAEvaluator(),
        promotion_decider=RuleBasedStageAPromotionDecider(),
    ).run(
        simulation_result,
        source_run_id="simulate.quality_deterioration.001",
    )
    candidate_id = stage_a_result.promoted_candidate_ids[0]
    validate_result = MultiPeriodValidateWorkflow(
        validate_workflow=ValidateWorkflow(
            validation_runner=RuleBasedValidationRunner(
                base_time=datetime(2026, 1, 18, 10, 30, tzinfo=timezone.utc)
            )
        ),
    ).run(
        source_run_id="validate.quality_deterioration.001",
        candidate_source_run_id="simulate.quality_deterioration.001",
        hypothesis=plan_result.hypothesis,
        blueprint=plan_result.blueprint,
        candidates=[
            evaluation.candidate
            for evaluation in synthesize_result.evaluations
            if evaluation.candidate.candidate_id == candidate_id
        ],
        validation_stage=ValidationStage.STAGE_B,
        periods=["P1Y0M0D", "P3Y0M0D", "P5Y0M0D"],
    )
    robust_result = RobustPromotionWorkflow(
        promotion_decider=RuleBasedRobustPromotionDecider(),
    ).run(
        validate_result,
        candidates=[
            evaluation.candidate
            for evaluation in synthesize_result.evaluations
            if evaluation.candidate.candidate_id == candidate_id
        ],
    )
    artifact_ledger = LocalFileArtifactLedger("artifacts")
    submission_ready_result = SubmissionReadyPromotionWorkflow().run(
        source_run_id="promote.quality_deterioration.001",
        robust_source_run_id="validate.quality_deterioration.001",
        hypothesis=plan_result.hypothesis,
        blueprint=plan_result.blueprint,
        robust_records=[
            artifact_ledger._validation_promotion_record_from_outcome(
                outcome,
                validation_stage=robust_result.validation_stage,
            )
            for outcome in robust_result.outcomes
            if outcome.promotion.to_stage == "robust_candidate"
        ],
        promoted_at=datetime(2026, 1, 18, 10, 45, tzinfo=timezone.utc),
    )
    submission_ready_record = artifact_ledger._submission_ready_record_from_outcome(
        submission_ready_result.outcomes[0]
    )
    review_result = HumanReviewWorkflow().run(
        source_run_id="review.quality_deterioration.001",
        submission_ready_source_run_id="promote.quality_deterioration.001",
        hypothesis=plan_result.hypothesis,
        blueprint=plan_result.blueprint,
        submission_ready_records=[submission_ready_record],
        reviewer="reviewer_01",
        decision=HumanReviewDecisionKind.APPROVE,
        reviewed_at=datetime(2026, 1, 18, 10, 50, tzinfo=timezone.utc),
        notes="ready for submission packet",
    )

    candidate_evaluation = next(
        evaluation
        for evaluation in synthesize_result.evaluations
        if evaluation.candidate.candidate_id == candidate_id
    )
    simulation_execution = next(
        execution
        for execution in simulation_result.executions
        if execution.simulation_request.candidate_id == candidate_id
    )
    stage_a_outcome = next(
        outcome
        for outcome in stage_a_result.outcomes
        if outcome.candidate.candidate_id == candidate_id
    )
    bundle = SubmissionPacketBundle(
        candidate_artifact=artifact_ledger._candidate_record_from_evaluation(candidate_evaluation),
        simulation_artifact=artifact_ledger._simulation_record_from_execution(simulation_execution),
        evaluation_artifact=artifact_ledger._evaluation_record_from_outcome(stage_a_outcome),
        stage_a_promotion=artifact_ledger._promotion_record_from_outcome(stage_a_outcome),
        submission_ready=submission_ready_record,
        validation_records=[
            outcome.validation
            for period_result in validate_result.period_results
            for outcome in period_result.outcomes
        ],
        review_decision=review_result.outcomes[0].review_decision,
    )

    result = SubmissionPacketWorkflow().run(
        source_run_id="packet.quality_deterioration.001",
        review_source_run_id="review.quality_deterioration.001",
        agenda=plan_result.agenda,
        hypothesis=plan_result.hypothesis,
        blueprint=plan_result.blueprint,
        bundles=[bundle],
        generated_at=datetime(2026, 1, 18, 11, 0, tzinfo=timezone.utc),
    )

    assert result.candidate_ids == [candidate_id]
    assert len(result.packets) == 1
    assert result.packets[0].packet_id == f"packet.packet.quality_deterioration.001.{candidate_id}"
    assert result.packets[0].validation_summary.aggregate_pass_decision is True
    assert result.packets[0].validation_summary.requested_periods == ["P1Y0M0D", "P3Y0M0D", "P5Y0M0D"]
    assert result.packets[0].review_decision.decision == HumanReviewDecisionKind.APPROVE
    assert result.packets[0].candidate_artifact.candidate.candidate_id == candidate_id
