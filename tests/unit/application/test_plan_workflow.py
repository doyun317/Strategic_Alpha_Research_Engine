from strategic_alpha_engine.application.services import StaticBlueprintBuilder, StaticHypothesisPlanner
from strategic_alpha_engine.application.workflows import PlanWorkflow
from strategic_alpha_engine.domain.examples import build_sample_research_agenda


def test_plan_workflow_builds_hypothesis_and_blueprint():
    workflow = PlanWorkflow(
        hypothesis_planner=StaticHypothesisPlanner(),
        blueprint_builder=StaticBlueprintBuilder(),
    )

    result = workflow.run(build_sample_research_agenda())

    assert result.hypothesis.agenda_id == result.agenda.agenda_id
    assert result.blueprint.hypothesis_id == result.hypothesis.hypothesis_id
