from __future__ import annotations

from strategic_alpha_engine.application.services.interfaces import BlueprintBuilder, HypothesisPlanner
from strategic_alpha_engine.domain.base import EngineModel
from strategic_alpha_engine.domain.hypothesis_spec import HypothesisSpec
from strategic_alpha_engine.domain.research_agenda import ResearchAgenda
from strategic_alpha_engine.domain.signal_blueprint import SignalBlueprint


class PlanResult(EngineModel):
    agenda: ResearchAgenda
    hypothesis: HypothesisSpec
    blueprint: SignalBlueprint


class PlanWorkflow:
    def __init__(
        self,
        hypothesis_planner: HypothesisPlanner,
        blueprint_builder: BlueprintBuilder,
    ):
        self.hypothesis_planner = hypothesis_planner
        self.blueprint_builder = blueprint_builder

    def run(self, agenda: ResearchAgenda) -> PlanResult:
        hypothesis = self.hypothesis_planner.plan(agenda)
        blueprint = self.blueprint_builder.build(hypothesis)
        return PlanResult(
            agenda=agenda,
            hypothesis=hypothesis,
            blueprint=blueprint,
        )
