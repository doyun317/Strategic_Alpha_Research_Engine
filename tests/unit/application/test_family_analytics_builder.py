from strategic_alpha_engine.application.services import (
    LocalArtifactFamilyAnalyticsBuilder,
    MetadataBackedStaticValidator,
    RuleBasedStrategicCritic,
    RuleBasedStageAEvaluator,
    RuleBasedStageAPromotionDecider,
    SkeletonCandidateSynthesizer,
    StaticBlueprintBuilder,
    StaticHypothesisPlanner,
)
from strategic_alpha_engine.application.workflows import (
    PlanWorkflow,
    SimulationExecutionPolicy,
    SimulationOrchestratorWorkflow,
    StageAEvaluationWorkflow,
    SynthesizeWorkflow,
)
from strategic_alpha_engine.domain.examples import build_sample_research_agenda
from strategic_alpha_engine.infrastructure import FakeBrainSimulationClient, LocalFileArtifactLedger
from strategic_alpha_engine.infrastructure.metadata import load_seed_metadata_catalog


def test_local_artifact_family_analytics_builder_derives_stats_and_learner_summary(tmp_path):
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

    artifact_ledger = LocalFileArtifactLedger(tmp_path / "artifacts")
    run_id = "simulate.quality_deterioration.001"
    artifact_ledger.write_plan_result(run_id, plan_result)
    artifact_ledger.write_synthesize_result(run_id, synthesize_result, agenda=plan_result.agenda)
    artifact_ledger.write_simulation_result(run_id, simulation_result)
    artifact_ledger.write_stage_a_result(run_id, stage_a_result)

    candidate_stage_records = []
    for outcome in stage_a_result.outcomes:
        candidate_stage_records.append(
            {
                "stage_record_id": f"stage.{run_id}.{outcome.candidate.candidate_id}.sim_passed",
                "candidate_id": outcome.candidate.candidate_id,
                "hypothesis_id": plan_result.hypothesis.hypothesis_id,
                "blueprint_id": plan_result.blueprint.blueprint_id,
                "family": plan_result.hypothesis.family,
                "stage": outcome.promotion.to_stage,
                "source_run_id": run_id,
                "recorded_at": outcome.promotion.decided_at,
            }
        )

    from strategic_alpha_engine.application.contracts import CandidateStageRecord

    analytics = LocalArtifactFamilyAnalyticsBuilder().build(
        tmp_path / "artifacts",
        candidate_stage_records=[CandidateStageRecord(**record) for record in candidate_stage_records],
    )

    assert analytics.family_stats[0].family == "quality_deterioration"
    assert analytics.family_stats[0].simulation_success_count == 4
    assert analytics.family_stats[0].stage_a_pass_rate == 1.0
    assert analytics.learner_summaries[0].median_stage_a_sharpe == 1.21
