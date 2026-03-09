import json

from strategic_alpha_engine.application.services import (
    MetadataBackedStaticValidator,
    RuleBasedRobustPromotionDecider,
    RuleBasedStrategicCritic,
    RuleBasedStageAEvaluator,
    RuleBasedStageAPromotionDecider,
    RuleBasedValidationRunner,
    SkeletonCandidateSynthesizer,
    StaticBlueprintBuilder,
    StaticHypothesisPlanner,
)
from strategic_alpha_engine.application.workflows import (
    HumanReviewWorkflow,
    MultiPeriodValidateWorkflow,
    PlanWorkflow,
    RobustPromotionWorkflow,
    SubmissionReadyPromotionWorkflow,
    SimulationExecutionPolicy,
    SimulationOrchestratorWorkflow,
    StageAEvaluationWorkflow,
    SynthesizeWorkflow,
    ValidateWorkflow,
)
from strategic_alpha_engine.domain.enums import HumanReviewDecisionKind, ValidationStage
from strategic_alpha_engine.domain.examples import build_sample_research_agenda
from strategic_alpha_engine.infrastructure import FakeBrainSimulationClient, LocalFileArtifactLedger
from strategic_alpha_engine.infrastructure.metadata import load_seed_metadata_catalog
from strategic_alpha_engine.interfaces.cli.main import _build_pending_human_review_queue_records
from strategic_alpha_engine.interfaces.cli.main import _build_submission_ready_inventory_records


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


def test_local_file_artifact_ledger_writes_validation_artifacts(tmp_path):
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
    ledger = LocalFileArtifactLedger(tmp_path / "artifacts")
    run_id = "validate.quality_deterioration.001"
    validate_result = MultiPeriodValidateWorkflow(
        validate_workflow=ValidateWorkflow(
            validation_runner=RuleBasedValidationRunner(),
        ),
    ).run(
        source_run_id=run_id,
        candidate_source_run_id="simulate.quality_deterioration.001",
        hypothesis=plan_result.hypothesis,
        blueprint=plan_result.blueprint,
        candidates=[evaluation.candidate for evaluation in synthesize_result.evaluations[:2]],
        validation_stage=ValidationStage.STAGE_B,
        periods=["P1Y0M0D", "P3Y0M0D", "P5Y0M0D"],
    )
    promotion_result = RobustPromotionWorkflow(
        promotion_decider=RuleBasedRobustPromotionDecider(),
    ).run(
        validate_result,
        candidates=[evaluation.candidate for evaluation in synthesize_result.evaluations[:2]],
    )
    submission_ready_result = SubmissionReadyPromotionWorkflow().run(
        source_run_id="promote.quality_deterioration.001",
        robust_source_run_id=run_id,
        hypothesis=plan_result.hypothesis,
        blueprint=plan_result.blueprint,
        robust_records=[
            ledger._validation_promotion_record_from_outcome(
                outcome,
                validation_stage=promotion_result.validation_stage,
            )
            for outcome in promotion_result.outcomes
            if outcome.promotion.to_stage == "robust_candidate"
        ],
        promoted_at=validate_result.period_results[0].outcomes[0].validation.validated_at,
    )
    submission_ready_inventory_records = _build_submission_ready_inventory_records(
        run_id="promote.quality_deterioration.001",
        hypothesis=plan_result.hypothesis,
        blueprint=plan_result.blueprint,
        promotion_result=submission_ready_result,
    )
    review_result = HumanReviewWorkflow().run(
        source_run_id="review.quality_deterioration.001",
        submission_ready_source_run_id="promote.quality_deterioration.001",
        hypothesis=plan_result.hypothesis,
        blueprint=plan_result.blueprint,
        submission_ready_records=[
            ledger._submission_ready_record_from_outcome(submission_ready_result.outcomes[0])
        ],
        reviewer="reviewer_01",
        decision=HumanReviewDecisionKind.APPROVE,
        reviewed_at=validate_result.period_results[0].outcomes[0].validation.validated_at,
    )
    pending_queue_records = _build_pending_human_review_queue_records(submission_ready_inventory_records)
    resolved_queue_records = [
        type(pending_queue_records[0])(
            **{
                **pending_queue_records[0].model_dump(mode="json"),
                "queue_record_id": (
                    "review_queue_update.review.quality_deterioration.001."
                    "cand.bp.quality_deterioration.001.001.approve"
                ),
                "status": "approved",
                "source_run_id": "review.quality_deterioration.001",
                "reviewer": "reviewer_01",
                "decision_id": review_result.outcomes[0].review_decision.decision_id,
                "updated_at": review_result.outcomes[0].review_decision.reviewed_at.isoformat().replace("+00:00", "Z"),
            }
        )
    ]

    ledger.write_validation_result(
        run_id,
        validate_result,
        agenda=plan_result.agenda,
    )
    ledger.write_robust_promotion_result(
        run_id,
        promotion_result,
    )
    ledger.write_submission_ready_result(
        "promote.quality_deterioration.001",
        submission_ready_result,
        agenda=plan_result.agenda,
    )
    ledger.write_human_review_result(
        "review.quality_deterioration.001",
        review_result,
        queue_records=resolved_queue_records,
        agenda=plan_result.agenda,
    )

    run_dir = tmp_path / "artifacts" / "runs" / run_id
    validations = _read_jsonl(run_dir / "validations.jsonl")
    matrix = _read_json(run_dir / "validation_matrix.json")
    robust_promotions = _read_jsonl(run_dir / "robust_promotion.jsonl")
    submission_ready = _read_jsonl(tmp_path / "artifacts" / "runs" / "promote.quality_deterioration.001" / "submission_ready.jsonl")
    human_review = _read_jsonl(tmp_path / "artifacts" / "runs" / "review.quality_deterioration.001" / "human_review.jsonl")
    review_queue = _read_jsonl(tmp_path / "artifacts" / "runs" / "review.quality_deterioration.001" / "review_queue.jsonl")

    assert _read_json(run_dir / "agenda.json")["agenda_id"] == "agenda.quality_deterioration.001"
    assert len(validations) == 6
    assert validations[0]["candidate"]["candidate_id"] == validations[0]["validation"]["candidate_id"]
    assert matrix["required_passing_periods"] == 2
    assert matrix["total_candidates"] == 2
    assert len(robust_promotions) == 2
    assert robust_promotions[0]["candidate"]["candidate_id"] == robust_promotions[0]["promotion"]["candidate_id"]
    assert len(submission_ready) == 2
    assert submission_ready[0]["candidate"]["candidate_id"] == submission_ready[0]["submission_promotion"]["candidate_id"]
    assert len(human_review) == 1
    assert human_review[0]["submission_ready"]["candidate"]["candidate_id"] == human_review[0]["review_decision"]["candidate_id"]
    assert len(review_queue) == 1
    assert review_queue[0]["status"] == "approved"
