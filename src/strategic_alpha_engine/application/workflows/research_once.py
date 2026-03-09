from __future__ import annotations

from pydantic import Field

from strategic_alpha_engine.application.services.interfaces import (
    BlueprintBuilder,
    CandidateSynthesizer,
    HypothesisPlanner,
    StaticValidator,
    StrategicCritic,
)
from strategic_alpha_engine.application.workflows.plan import PlanWorkflow
from strategic_alpha_engine.application.workflows.synthesize import CandidateEvaluation, SynthesizeWorkflow
from strategic_alpha_engine.domain.base import EngineModel
from strategic_alpha_engine.domain.hypothesis_spec import HypothesisSpec
from strategic_alpha_engine.domain.research_agenda import ResearchAgenda
from strategic_alpha_engine.domain.signal_blueprint import SignalBlueprint


class ResearchOnceResult(EngineModel):
    agenda: ResearchAgenda
    hypothesis: HypothesisSpec
    blueprint: SignalBlueprint
    evaluations: list[CandidateEvaluation] = Field(default_factory=list)
    accepted_candidate_ids: list[str] = Field(default_factory=list)
    rejected_candidate_ids: list[str] = Field(default_factory=list)


class ResearchOnceWorkflow:
    def __init__(
        self,
        hypothesis_planner: HypothesisPlanner,
        blueprint_builder: BlueprintBuilder,
        candidate_synthesizer: CandidateSynthesizer,
        static_validator: StaticValidator,
        strategic_critic: StrategicCritic,
    ):
        self.hypothesis_planner = hypothesis_planner
        self.blueprint_builder = blueprint_builder
        self.candidate_synthesizer = candidate_synthesizer
        self.static_validator = static_validator
        self.strategic_critic = strategic_critic
        self.plan_workflow = PlanWorkflow(
            hypothesis_planner=hypothesis_planner,
            blueprint_builder=blueprint_builder,
        )
        self.synthesize_workflow = SynthesizeWorkflow(
            candidate_synthesizer=candidate_synthesizer,
            static_validator=static_validator,
            strategic_critic=strategic_critic,
        )

    def run(self, agenda: ResearchAgenda) -> ResearchOnceResult:
        plan_result = self.plan_workflow.run(agenda)
        synthesize_result = self.synthesize_workflow.run(
            hypothesis=plan_result.hypothesis,
            blueprint=plan_result.blueprint,
        )

        return ResearchOnceResult(
            agenda=agenda,
            hypothesis=plan_result.hypothesis,
            blueprint=plan_result.blueprint,
            evaluations=synthesize_result.evaluations,
            accepted_candidate_ids=synthesize_result.accepted_candidate_ids,
            rejected_candidate_ids=synthesize_result.rejected_candidate_ids,
        )
