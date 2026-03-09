import json

from strategic_alpha_engine.application.services import (
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


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path):
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        return []
    return [json.loads(line) for line in content.splitlines()]


def test_local_file_artifact_ledger_writes_plan_synthesis_and_simulation_artifacts(tmp_path):
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
        source_run_id="run.quality_deterioration.001",
    )
    ledger = LocalFileArtifactLedger(tmp_path / "artifacts")
    run_id = "run.quality_deterioration.001"

    ledger.write_plan_result(run_id, plan_result)
    ledger.write_synthesize_result(run_id, synthesize_result, agenda=plan_result.agenda)
    ledger.write_simulation_result(run_id, simulation_result)
    ledger.write_stage_a_result(run_id, stage_a_result)

    run_dir = tmp_path / "artifacts" / "runs" / run_id

    assert run_dir.exists()
    assert _read_json(run_dir / "agenda.json")["agenda_id"] == "agenda.quality_deterioration.001"
    assert _read_json(run_dir / "hypothesis.json")["hypothesis_id"] == "hyp.quality_deterioration.001"
    assert _read_json(run_dir / "blueprint.json")["blueprint_id"] == "bp.quality_deterioration.001"
    assert len(_read_jsonl(run_dir / "candidates.jsonl")) == 4
    assert len(_read_jsonl(run_dir / "validations.jsonl")) == 4
    assert len(_read_jsonl(run_dir / "critiques.jsonl")) == 4
    simulations = _read_jsonl(run_dir / "simulations.jsonl")
    assert len(simulations) == 4
    assert simulations[0]["simulation_request"]["candidate_id"] == simulations[0]["result"]["candidate_id"]
    assert simulations[0]["simulation_run"]["provider_run_id"] == simulations[0]["submission"]["provider_run_id"]
    evaluations = _read_jsonl(run_dir / "evaluations.jsonl")
    promotions = _read_jsonl(run_dir / "promotion.jsonl")
    assert len(evaluations) == 4
    assert len(promotions) == 4
    assert evaluations[0]["evaluation"]["candidate_id"] == promotions[0]["promotion"]["candidate_id"]


def test_local_file_artifact_ledger_keeps_existing_agenda_when_writing_simulation_only(tmp_path):
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
        source_run_id="run.quality_deterioration.002",
    )
    ledger = LocalFileArtifactLedger(tmp_path / "artifacts")
    run_id = "run.quality_deterioration.002"

    ledger.write_plan_result(run_id, plan_result)
    ledger.write_simulation_result(run_id, simulation_result)
    ledger.write_stage_a_result(run_id, stage_a_result)

    run_dir = tmp_path / "artifacts" / "runs" / run_id

    assert _read_json(run_dir / "agenda.json")["agenda_id"] == "agenda.quality_deterioration.001"
    assert len(_read_jsonl(run_dir / "simulations.jsonl")) == 4
    assert len(_read_jsonl(run_dir / "promotion.jsonl")) == 4
