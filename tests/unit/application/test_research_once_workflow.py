from strategic_alpha_engine.application.services import (
    RuleBasedStrategicCritic,
    SkeletonCandidateSynthesizer,
    StaticBlueprintBuilder,
    StaticHypothesisPlanner,
)
from strategic_alpha_engine.application.workflows import ResearchOnceWorkflow
from strategic_alpha_engine.domain.examples import build_sample_research_agenda


def test_research_once_workflow_runs_end_to_end():
    workflow = ResearchOnceWorkflow(
        hypothesis_planner=StaticHypothesisPlanner(),
        blueprint_builder=StaticBlueprintBuilder(),
        candidate_synthesizer=SkeletonCandidateSynthesizer(),
        strategic_critic=RuleBasedStrategicCritic(),
    )

    result = workflow.run(build_sample_research_agenda())

    assert result.hypothesis.agenda_id == result.agenda.agenda_id
    assert result.blueprint.hypothesis_id == result.hypothesis.hypothesis_id
    assert len(result.evaluations) == result.blueprint.target_expression_count
    assert len(result.accepted_candidate_ids) + len(result.rejected_candidate_ids) == len(
        result.evaluations
    )
