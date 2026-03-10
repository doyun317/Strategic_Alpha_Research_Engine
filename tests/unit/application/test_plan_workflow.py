from strategic_alpha_engine.domain.examples import build_sample_research_agenda
from strategic_alpha_engine.testing import build_sample_plan_workflow


def test_plan_workflow_builds_hypothesis_and_blueprint():
    workflow = build_sample_plan_workflow()

    result = workflow.run(build_sample_research_agenda())

    assert result.hypothesis.agenda_id == result.agenda.agenda_id
    assert result.blueprint.hypothesis_id == result.hypothesis.hypothesis_id
