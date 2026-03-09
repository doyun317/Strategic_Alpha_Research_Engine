from datetime import datetime, timezone

from strategic_alpha_engine.application.workflows import HumanReviewWorkflow
from strategic_alpha_engine.infrastructure import LocalFileArtifactLedger
from strategic_alpha_engine.infrastructure.metadata import load_seed_metadata_catalog
from strategic_alpha_engine.application.services import (
    MetadataBackedStaticValidator,
    RuleBasedRobustPromotionDecider,
    RuleBasedStrategicCritic,
    RuleBasedValidationRunner,
    SkeletonCandidateSynthesizer,
    StaticBlueprintBuilder,
    StaticHypothesisPlanner,
)
from strategic_alpha_engine.application.workflows import (
    MultiPeriodValidateWorkflow,
    PlanWorkflow,
    RobustPromotionWorkflow,
    SubmissionReadyPromotionWorkflow,
    SynthesizeWorkflow,
    ValidateWorkflow,
)
from strategic_alpha_engine.domain.enums import HumanReviewDecisionKind, ValidationStage
from strategic_alpha_engine.domain.examples import build_sample_research_agenda


def test_human_review_workflow_holds_submission_ready_candidate():
    plan_result = PlanWorkflow(
        hypothesis_planner=StaticHypothesisPlanner(),
        blueprint_builder=StaticBlueprintBuilder(),
    ).run(build_sample_research_agenda())
    synthesize_result = SynthesizeWorkflow(
        candidate_synthesizer=SkeletonCandidateSynthesizer(),
        static_validator=MetadataBackedStaticValidator(load_seed_metadata_catalog()),
        strategic_critic=RuleBasedStrategicCritic(),
    ).run(
        hypothesis=plan_result.hypothesis,
        blueprint=plan_result.blueprint,
    )
    validate_result = MultiPeriodValidateWorkflow(
        validate_workflow=ValidateWorkflow(
            validation_runner=RuleBasedValidationRunner(),
        ),
    ).run(
        source_run_id="validate.quality_deterioration.001",
        candidate_source_run_id="simulate.quality_deterioration.001",
        hypothesis=plan_result.hypothesis,
        blueprint=plan_result.blueprint,
        candidates=[evaluation.candidate for evaluation in synthesize_result.evaluations[:2]],
        validation_stage=ValidationStage.STAGE_B,
        periods=["P1Y0M0D", "P3Y0M0D", "P5Y0M0D"],
    )
    robust_result = RobustPromotionWorkflow(
        promotion_decider=RuleBasedRobustPromotionDecider(),
    ).run(
        validate_result,
        candidates=[evaluation.candidate for evaluation in synthesize_result.evaluations[:2]],
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
        promoted_at=datetime(2026, 1, 15, 15, 10, tzinfo=timezone.utc),
    )

    result = HumanReviewWorkflow().run(
        source_run_id="review.quality_deterioration.001",
        submission_ready_source_run_id="promote.quality_deterioration.001",
        hypothesis=plan_result.hypothesis,
        blueprint=plan_result.blueprint,
        submission_ready_records=[
            artifact_ledger._submission_ready_record_from_outcome(submission_ready_result.outcomes[0])
        ],
        reviewer="reviewer_01",
        decision=HumanReviewDecisionKind.HOLD,
        reviewed_at=datetime(2026, 1, 15, 15, 15, tzinfo=timezone.utc),
        notes="needs extra manual comparison",
    )

    assert result.reviewed_candidate_ids == ["cand.bp.quality_deterioration.001.001"]
    assert result.held_candidate_ids == ["cand.bp.quality_deterioration.001.001"]
    assert result.outcomes[0].review_decision.to_stage == "robust_candidate"
    assert result.outcomes[0].review_decision.reviewer == "reviewer_01"
