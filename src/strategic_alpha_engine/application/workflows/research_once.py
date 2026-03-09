from __future__ import annotations

from pydantic import Field

from strategic_alpha_engine.application.services.interfaces import (
    BlueprintBuilder,
    CandidateSynthesizer,
    HypothesisPlanner,
    StrategicCritic,
)
from strategic_alpha_engine.domain.base import EngineModel
from strategic_alpha_engine.domain.critique_report import CritiqueReport
from strategic_alpha_engine.domain.expression_candidate import ExpressionCandidate
from strategic_alpha_engine.domain.hypothesis_spec import HypothesisSpec
from strategic_alpha_engine.domain.research_agenda import ResearchAgenda
from strategic_alpha_engine.domain.signal_blueprint import SignalBlueprint


class CandidateEvaluation(EngineModel):
    candidate: ExpressionCandidate
    critique: CritiqueReport


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
        strategic_critic: StrategicCritic,
    ):
        self.hypothesis_planner = hypothesis_planner
        self.blueprint_builder = blueprint_builder
        self.candidate_synthesizer = candidate_synthesizer
        self.strategic_critic = strategic_critic

    def run(self, agenda: ResearchAgenda) -> ResearchOnceResult:
        hypothesis = self.hypothesis_planner.plan(agenda)
        blueprint = self.blueprint_builder.build(hypothesis)
        candidates = self.candidate_synthesizer.synthesize(blueprint)

        evaluations: list[CandidateEvaluation] = []
        accepted: list[str] = []
        rejected: list[str] = []

        for candidate in candidates:
            critique = self.strategic_critic.critique(hypothesis, blueprint, candidate)
            evaluations.append(CandidateEvaluation(candidate=candidate, critique=critique))
            if critique.passes:
                accepted.append(candidate.candidate_id)
            else:
                rejected.append(candidate.candidate_id)

        return ResearchOnceResult(
            agenda=agenda,
            hypothesis=hypothesis,
            blueprint=blueprint,
            evaluations=evaluations,
            accepted_candidate_ids=accepted,
            rejected_candidate_ids=rejected,
        )

