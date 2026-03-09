from __future__ import annotations

from pydantic import Field

from strategic_alpha_engine.application.contracts.simulation import BrainSimulationResult
from strategic_alpha_engine.application.services.interfaces import PromotionDecider, StageAEvaluator
from strategic_alpha_engine.domain.base import EngineModel
from strategic_alpha_engine.domain.evaluation import EvaluationRecord
from strategic_alpha_engine.domain.enums import (
    CandidateLifecycleStage,
    EvaluationStage,
    PromotionDecisionKind,
    SimulationStatus,
)
from strategic_alpha_engine.domain.promotion import PromotionDecision
from strategic_alpha_engine.domain.simulation import SimulationRequest, SimulationRun


class StageAThresholds(EngineModel):
    min_sharpe: float = Field(default=0.7, ge=-10.0, le=10.0)
    min_fitness: float = Field(default=0.2, ge=-10.0, le=10.0)
    min_turnover: float = Field(default=0.01, ge=0.0, le=10.0)
    max_turnover: float = Field(default=0.7, ge=0.0, le=10.0)


class RuleBasedStageAEvaluator(StageAEvaluator):
    def __init__(self, thresholds: StageAThresholds | None = None):
        self.thresholds = thresholds or StageAThresholds()

    def evaluate(
        self,
        simulation_request: SimulationRequest,
        simulation_run: SimulationRun,
        result: BrainSimulationResult,
        *,
        source_run_id: str,
    ) -> EvaluationRecord:
        reasons: list[str] = []
        pass_decision = result.status == SimulationStatus.SUCCEEDED

        if result.status != SimulationStatus.SUCCEEDED:
            reasons.append(f"simulation_status_{result.status}")
        else:
            if result.sharpe is not None and result.sharpe < self.thresholds.min_sharpe:
                reasons.append("sharpe_below_stage_a_threshold")
                pass_decision = False
            if result.fitness is not None and result.fitness < self.thresholds.min_fitness:
                reasons.append("fitness_below_stage_a_threshold")
                pass_decision = False
            if result.turnover is not None and result.turnover < self.thresholds.min_turnover:
                reasons.append("turnover_below_stage_a_band")
                pass_decision = False
            if result.turnover is not None and result.turnover > self.thresholds.max_turnover:
                reasons.append("turnover_above_stage_a_band")
                pass_decision = False

        if pass_decision:
            reasons.append("meets_stage_a_thresholds")

        return EvaluationRecord(
            evaluation_id=f"eval.{source_run_id}.{simulation_request.candidate_id}.stage_a",
            candidate_id=simulation_request.candidate_id,
            hypothesis_id=simulation_request.hypothesis_id,
            blueprint_id=simulation_request.blueprint_id,
            simulation_request_id=simulation_request.simulation_request_id,
            simulation_run_id=simulation_run.simulation_run_id,
            source_run_id=source_run_id,
            evaluation_stage=EvaluationStage.STAGE_A,
            period=simulation_request.test_period,
            status=result.status,
            sharpe=result.sharpe,
            fitness=result.fitness,
            turnover=result.turnover,
            returns=result.returns,
            drawdown=result.drawdown,
            checks=result.checks,
            grade=result.grade,
            pass_decision=pass_decision,
            reasons=reasons,
            evaluated_at=result.completed_at,
        )


class RuleBasedStageAPromotionDecider(PromotionDecider):
    def decide(self, evaluation: EvaluationRecord) -> PromotionDecision:
        decision = (
            PromotionDecisionKind.PROMOTE
            if evaluation.pass_decision
            else PromotionDecisionKind.REJECT
        )
        to_stage = (
            CandidateLifecycleStage.SIM_PASSED
            if evaluation.pass_decision
            else CandidateLifecycleStage.REJECTED
        )
        reasons = ["stage_a_passed"] if evaluation.pass_decision else list(evaluation.reasons)

        return PromotionDecision(
            promotion_id=f"promotion.{evaluation.source_run_id}.{evaluation.candidate_id}.stage_a",
            candidate_id=evaluation.candidate_id,
            hypothesis_id=evaluation.hypothesis_id,
            blueprint_id=evaluation.blueprint_id,
            evaluation_id=evaluation.evaluation_id,
            source_run_id=evaluation.source_run_id,
            from_stage=CandidateLifecycleStage.CRITIQUE_PASSED,
            to_stage=to_stage,
            decision=decision,
            reasons=reasons,
            decided_at=evaluation.evaluated_at,
        )
