from __future__ import annotations

from pathlib import Path
from typing import Protocol

from strategic_alpha_engine.application.contracts.artifacts import (
    CandidateArtifactRecord,
    EvaluationArtifactRecord,
    PromotionArtifactRecord,
    SimulationArtifactRecord,
    ValidationArtifactRecord,
)
from strategic_alpha_engine.application.contracts.simulation import (
    BrainSimulationPollResult,
    BrainSimulationResult,
    BrainSimulationSubmission,
)
from strategic_alpha_engine.application.contracts.state import (
    AgendaQueueRecord,
    CandidateStageRecord,
    FamilyLearnerSummary,
    FamilyStatsSnapshot,
    RunStateRecord,
    ValidationBacklogEntry,
)
from strategic_alpha_engine.domain.evaluation import EvaluationRecord
from strategic_alpha_engine.domain.critique_report import CritiqueReport
from strategic_alpha_engine.domain.expression_candidate import ExpressionCandidate
from strategic_alpha_engine.domain.hypothesis_spec import HypothesisSpec
from strategic_alpha_engine.domain.promotion import PromotionDecision
from strategic_alpha_engine.domain.research_agenda import ResearchAgenda
from strategic_alpha_engine.domain.search_policy import (
    AgendaSelection,
    AgendaPriorityRecommendation,
    FamilyPolicyRecommendation,
)
from strategic_alpha_engine.domain.signal_blueprint import SignalBlueprint
from strategic_alpha_engine.domain.simulation import SimulationRequest, SimulationRun
from strategic_alpha_engine.domain.static_validation import StaticValidationReport
from strategic_alpha_engine.domain.enums import ValidationStage
from strategic_alpha_engine.domain.validation import ValidationRecord


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


class StageAEvaluator(Protocol):
    def evaluate(
        self,
        simulation_request: SimulationRequest,
        simulation_run: SimulationRun,
        result: BrainSimulationResult,
        *,
        source_run_id: str,
    ) -> EvaluationRecord: ...


class PromotionDecider(Protocol):
    def decide(self, evaluation: EvaluationRecord) -> PromotionDecision: ...


class ValidationRunner(Protocol):
    def validate(
        self,
        candidate: ExpressionCandidate,
        hypothesis: HypothesisSpec,
        blueprint: SignalBlueprint,
        *,
        source_run_id: str,
        candidate_source_run_id: str,
        validation_stage: ValidationStage,
        period: str,
    ) -> ValidationRecord: ...


class FamilyAnalyticsBuilder(Protocol):
    def build(
        self,
        root_dir: str | Path,
        *,
        candidate_stage_records: list[CandidateStageRecord],
    ): ...


class SearchPolicyLearner(Protocol):
    def recommend(
        self,
        summaries: list[FamilyLearnerSummary],
    ) -> list[FamilyPolicyRecommendation]: ...


class AgendaPrioritizer(Protocol):
    def prioritize(
        self,
        agendas: list[ResearchAgenda],
        family_recommendations: list[FamilyPolicyRecommendation],
    ) -> list[AgendaPriorityRecommendation]: ...


class ResearchAgendaManager(Protocol):
    def select_next(
        self,
        agendas: list[ResearchAgenda],
        family_recommendations: list[FamilyPolicyRecommendation],
        *,
        excluded_agenda_ids: set[str] | None = None,
    ) -> AgendaSelection: ...


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

    def write_evaluation_records(
        self,
        run_id: str,
        records: list[EvaluationArtifactRecord],
    ) -> Path: ...

    def write_promotion_records(
        self,
        run_id: str,
        records: list[PromotionArtifactRecord],
    ) -> Path: ...

    def write_validation_records(
        self,
        run_id: str,
        records: list[ValidationArtifactRecord],
    ) -> Path: ...

    def write_validation_matrix(
        self,
        run_id: str,
        payload: dict,
    ) -> Path: ...


class StateLedger(Protocol):
    def append_candidate_stage_records(self, records: list[CandidateStageRecord]) -> Path: ...

    def append_run_state_records(self, records: list[RunStateRecord]) -> Path: ...

    def append_agenda_queue_records(self, records: list[AgendaQueueRecord]) -> Path: ...

    def write_family_stats(self, snapshots: list[FamilyStatsSnapshot]) -> Path: ...

    def write_family_learner_summaries(self, summaries: list[FamilyLearnerSummary]) -> Path: ...

    def append_validation_backlog_entries(self, entries: list[ValidationBacklogEntry]) -> Path: ...

    def load_candidate_stage_records(self) -> list[CandidateStageRecord]: ...

    def load_run_state_records(self) -> list[RunStateRecord]: ...

    def load_agenda_queue_records(self) -> list[AgendaQueueRecord]: ...

    def load_family_stats(self) -> list[FamilyStatsSnapshot]: ...

    def load_family_learner_summaries(self) -> list[FamilyLearnerSummary]: ...

    def load_validation_backlog_entries(self) -> list[ValidationBacklogEntry]: ...
