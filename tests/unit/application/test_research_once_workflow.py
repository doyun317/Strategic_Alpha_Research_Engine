from strategic_alpha_engine.application.services import (
    MetadataBackedStaticValidator,
    RuleBasedStrategicCritic,
    SkeletonCandidateSynthesizer,
    StaticBlueprintBuilder,
    StaticHypothesisPlanner,
)
from strategic_alpha_engine.application.workflows import ResearchOnceWorkflow
from strategic_alpha_engine.domain.examples import build_sample_expression_candidate, build_sample_research_agenda
from strategic_alpha_engine.infrastructure.metadata import load_seed_metadata_catalog


def test_research_once_workflow_runs_end_to_end():
    workflow = ResearchOnceWorkflow(
        hypothesis_planner=StaticHypothesisPlanner(),
        blueprint_builder=StaticBlueprintBuilder(),
        candidate_synthesizer=SkeletonCandidateSynthesizer(),
        static_validator=MetadataBackedStaticValidator(load_seed_metadata_catalog()),
        strategic_critic=RuleBasedStrategicCritic(),
    )

    result = workflow.run(build_sample_research_agenda())

    assert result.hypothesis.agenda_id == result.agenda.agenda_id
    assert result.blueprint.hypothesis_id == result.hypothesis.hypothesis_id
    assert len(result.evaluations) == result.blueprint.target_expression_count
    assert all(evaluation.validation.passes is True for evaluation in result.evaluations)
    assert all(evaluation.critique is not None for evaluation in result.evaluations)
    assert len(result.accepted_candidate_ids) + len(result.rejected_candidate_ids) == len(
        result.evaluations
    )


def test_research_once_workflow_rejects_candidate_before_critique_when_static_validation_fails():
    class InvalidCandidateSynthesizer:
        def synthesize(self, blueprint):
            return [
                build_sample_expression_candidate().model_copy(
                    update={"candidate_id": "cand.invalid.001", "expression": "rank(foo(cashflow_op))"}
                )
            ]

    workflow = ResearchOnceWorkflow(
        hypothesis_planner=StaticHypothesisPlanner(),
        blueprint_builder=StaticBlueprintBuilder(),
        candidate_synthesizer=InvalidCandidateSynthesizer(),
        static_validator=MetadataBackedStaticValidator(load_seed_metadata_catalog()),
        strategic_critic=RuleBasedStrategicCritic(),
    )

    result = workflow.run(build_sample_research_agenda())

    assert result.accepted_candidate_ids == []
    assert result.rejected_candidate_ids == ["cand.invalid.001"]
    assert result.evaluations[0].validation.passes is False
    assert result.evaluations[0].critique is None
