from __future__ import annotations

from pathlib import Path
from typing import Protocol

from strategic_alpha_engine.application.contracts.artifacts import (
    CandidateArtifactRecord,
    SimulationArtifactRecord,
)
from strategic_alpha_engine.application.contracts.simulation import (
    BrainSimulationPollResult,
    BrainSimulationResult,
    BrainSimulationSubmission,
)
from strategic_alpha_engine.domain.critique_report import CritiqueReport
from strategic_alpha_engine.domain.expression_candidate import ExpressionCandidate
from strategic_alpha_engine.domain.hypothesis_spec import HypothesisSpec
from strategic_alpha_engine.domain.research_agenda import ResearchAgenda
from strategic_alpha_engine.domain.signal_blueprint import SignalBlueprint
from strategic_alpha_engine.domain.simulation import SimulationRequest
from strategic_alpha_engine.domain.static_validation import StaticValidationReport


class HypothesisPlanner(Protocol):
    def plan(self, agenda: ResearchAgenda) -> HypothesisSpec: ...


class BlueprintBuilder(Protocol):
    def build(self, hypothesis: HypothesisSpec) -> SignalBlueprint: ...


class CandidateSynthesizer(Protocol):
    def synthesize(self, blueprint: SignalBlueprint) -> list[ExpressionCandidate]: ...


class StaticValidator(Protocol):
    def validate(
        self,
        blueprint: SignalBlueprint,
        candidate: ExpressionCandidate,
    ) -> StaticValidationReport: ...


class StrategicCritic(Protocol):
    def critique(
        self,
        hypothesis: HypothesisSpec,
        blueprint: SignalBlueprint,
        candidate: ExpressionCandidate,
    ) -> CritiqueReport: ...


class BrainSimulationClient(Protocol):
    def submit(self, request: SimulationRequest) -> BrainSimulationSubmission: ...

    def poll(self, provider_run_id: str) -> BrainSimulationPollResult: ...

    def fetch_result(self, provider_run_id: str) -> BrainSimulationResult: ...


class ArtifactLedger(Protocol):
    def write_context(
        self,
        run_id: str,
        *,
        agenda: ResearchAgenda | None,
        hypothesis: HypothesisSpec,
        blueprint: SignalBlueprint,
    ) -> Path: ...

    def write_candidate_records(
        self,
        run_id: str,
        records: list[CandidateArtifactRecord],
    ) -> Path: ...

    def write_simulation_records(
        self,
        run_id: str,
        records: list[SimulationArtifactRecord],
    ) -> Path: ...
