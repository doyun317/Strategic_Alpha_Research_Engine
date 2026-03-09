from __future__ import annotations

from typing import Protocol

from strategic_alpha_engine.domain.critique_report import CritiqueReport
from strategic_alpha_engine.domain.expression_candidate import ExpressionCandidate
from strategic_alpha_engine.domain.hypothesis_spec import HypothesisSpec
from strategic_alpha_engine.domain.research_agenda import ResearchAgenda
from strategic_alpha_engine.domain.signal_blueprint import SignalBlueprint


class HypothesisPlanner(Protocol):
    def plan(self, agenda: ResearchAgenda) -> HypothesisSpec: ...


class BlueprintBuilder(Protocol):
    def build(self, hypothesis: HypothesisSpec) -> SignalBlueprint: ...


class CandidateSynthesizer(Protocol):
    def synthesize(self, blueprint: SignalBlueprint) -> list[ExpressionCandidate]: ...


class StrategicCritic(Protocol):
    def critique(
        self,
        hypothesis: HypothesisSpec,
        blueprint: SignalBlueprint,
        candidate: ExpressionCandidate,
    ) -> CritiqueReport: ...

