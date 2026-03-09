from __future__ import annotations

from pydantic import Field

from strategic_alpha_engine.application.services.interfaces import PromotionDecider, StageAEvaluator
from strategic_alpha_engine.application.workflows.simulate import (
    SimulationCandidateExecution,
    SimulationOrchestratorResult,
)
from strategic_alpha_engine.domain.base import EngineModel
from strategic_alpha_engine.domain.critique_report import CritiqueReport
from strategic_alpha_engine.domain.evaluation import EvaluationRecord
from strategic_alpha_engine.domain.expression_candidate import ExpressionCandidate
from strategic_alpha_engine.domain.hypothesis_spec import HypothesisSpec
from strategic_alpha_engine.domain.promotion import PromotionDecision
from strategic_alpha_engine.domain.signal_blueprint import SignalBlueprint


class StageACandidateOutcome(EngineModel):
    candidate: ExpressionCandidate
    critique: CritiqueReport
    execution: SimulationCandidateExecution
    evaluation: EvaluationRecord
    promotion: PromotionDecision


class StageAEvaluationResult(EngineModel):
    source_run_id: str
    hypothesis: HypothesisSpec
    blueprint: SignalBlueprint
    outcomes: list[StageACandidateOutcome] = Field(default_factory=list)
    promoted_candidate_ids: list[str] = Field(default_factory=list)
    rejected_candidate_ids: list[str] = Field(default_factory=list)


class StageAEvaluationWorkflow:
    def __init__(
        self,
        evaluator: StageAEvaluator,
        promotion_decider: PromotionDecider,
    ):
        self.evaluator = evaluator
        self.promotion_decider = promotion_decider

    def run(
        self,
        simulation_result: SimulationOrchestratorResult,
        *,
        source_run_id: str,
    ) -> StageAEvaluationResult:
        outcomes: list[StageACandidateOutcome] = []
        promoted_candidate_ids: list[str] = []
        rejected_candidate_ids: list[str] = []

        for execution in simulation_result.executions:
            evaluation = self.evaluator.evaluate(
                execution.simulation_request,
                execution.simulation_run,
                execution.result,
                source_run_id=source_run_id,
            )
            promotion = self.promotion_decider.decide(evaluation)
            outcomes.append(
                StageACandidateOutcome(
                    candidate=execution.candidate,
                    critique=execution.critique,
                    execution=execution,
                    evaluation=evaluation,
                    promotion=promotion,
                )
            )
            if promotion.to_stage == "sim_passed":
                promoted_candidate_ids.append(execution.candidate.candidate_id)
            elif promotion.to_stage == "rejected":
                rejected_candidate_ids.append(execution.candidate.candidate_id)

        return StageAEvaluationResult(
            source_run_id=source_run_id,
            hypothesis=simulation_result.hypothesis,
            blueprint=simulation_result.blueprint,
            outcomes=outcomes,
            promoted_candidate_ids=promoted_candidate_ids,
            rejected_candidate_ids=rejected_candidate_ids,
        )
