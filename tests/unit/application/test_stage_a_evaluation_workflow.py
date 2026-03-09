from strategic_alpha_engine.application.services import (
    RuleBasedStageAEvaluator,
    RuleBasedStageAPromotionDecider,
)
from strategic_alpha_engine.application.workflows import (
    SimulationExecutionPolicy,
    SimulationOrchestratorWorkflow,
    StageAEvaluationWorkflow,
)
from strategic_alpha_engine.domain.enums import SimulationStatus
from strategic_alpha_engine.domain.examples import (
    build_sample_expression_candidate,
    build_sample_hypothesis_spec,
    build_sample_signal_blueprint,
)
from strategic_alpha_engine.domain.critique_report import CritiqueReport
from strategic_alpha_engine.domain.static_validation import StaticValidationReport
from strategic_alpha_engine.infrastructure import FakeBrainSimulationClient
from strategic_alpha_engine.application.workflows.synthesize import CandidateEvaluation, SynthesizeResult


def _build_validation(candidate_id: str) -> StaticValidationReport:
    return StaticValidationReport(
        validation_id=f"static.validation.{candidate_id}",
        candidate_id=candidate_id,
        blueprint_id="bp.quality_deterioration.001",
        passes=True,
        checked_operator_count=5,
        checked_field_count=2,
        issues=[],
    )


def _build_critique(candidate_id: str) -> CritiqueReport:
    return CritiqueReport(
        critique_id=f"critique.{candidate_id}",
        candidate_id=candidate_id,
        blueprint_id="bp.quality_deterioration.001",
        passes=True,
        overall_score=0.88,
        structural_quality_score=0.9,
        economic_coherence_score=0.86,
        data_horizon_alignment_score=0.88,
        issues=[],
        repair_suggestions=[],
        tags=["quality"],
    )


def _build_synthesize_result() -> SynthesizeResult:
    candidate = build_sample_expression_candidate().model_copy(update={"candidate_id": "cand.stage_a.001"})
    return SynthesizeResult(
        hypothesis=build_sample_hypothesis_spec(),
        blueprint=build_sample_signal_blueprint(),
        evaluations=[
            CandidateEvaluation(
                candidate=candidate,
                validation=_build_validation(candidate.candidate_id),
                critique=_build_critique(candidate.candidate_id),
            )
        ],
        accepted_candidate_ids=[candidate.candidate_id],
        rejected_candidate_ids=[],
    )


def test_stage_a_workflow_promotes_candidates_that_meet_thresholds():
    simulation_result = SimulationOrchestratorWorkflow(
        brain_client=FakeBrainSimulationClient(),
        max_polls=3,
    ).run(
        synthesize_result=_build_synthesize_result(),
        policy=SimulationExecutionPolicy(),
    )

    result = StageAEvaluationWorkflow(
        evaluator=RuleBasedStageAEvaluator(),
        promotion_decider=RuleBasedStageAPromotionDecider(),
    ).run(
        simulation_result,
        source_run_id="simulate.quality_deterioration.001",
    )

    assert result.promoted_candidate_ids == ["cand.stage_a.001"]
    assert result.rejected_candidate_ids == []
    assert result.outcomes[0].evaluation.pass_decision is True
    assert result.outcomes[0].promotion.to_stage == "sim_passed"


def test_stage_a_workflow_rejects_candidates_that_fail_thresholds():
    simulation_result = SimulationOrchestratorWorkflow(
        brain_client=FakeBrainSimulationClient(
            terminal_status=SimulationStatus.SUCCEEDED,
            metric_seed={
                "sharpe": 0.41,
                "fitness": 0.1,
                "turnover": 0.9,
                "returns": 0.04,
                "drawdown": 0.11,
            },
        ),
        max_polls=3,
    ).run(
        synthesize_result=_build_synthesize_result(),
        policy=SimulationExecutionPolicy(),
    )

    result = StageAEvaluationWorkflow(
        evaluator=RuleBasedStageAEvaluator(),
        promotion_decider=RuleBasedStageAPromotionDecider(),
    ).run(
        simulation_result,
        source_run_id="simulate.quality_deterioration.002",
    )

    assert result.promoted_candidate_ids == []
    assert result.rejected_candidate_ids == ["cand.stage_a.001"]
    assert result.outcomes[0].evaluation.pass_decision is False
    assert "sharpe_below_stage_a_threshold" in result.outcomes[0].evaluation.reasons
    assert result.outcomes[0].promotion.to_stage == "rejected"
