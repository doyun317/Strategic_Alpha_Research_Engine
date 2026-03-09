from __future__ import annotations

from datetime import datetime, timezone

from strategic_alpha_engine.application.services.interfaces import ValidationRunner
from strategic_alpha_engine.domain.enums import SimulationStatus, ValidationStage
from strategic_alpha_engine.domain.expression_candidate import ExpressionCandidate
from strategic_alpha_engine.domain.hypothesis_spec import HypothesisSpec
from strategic_alpha_engine.domain.signal_blueprint import SignalBlueprint
from strategic_alpha_engine.domain.validation import ValidationRecord

_PERIOD_FACTORS = {
    "P1Y0M0D": 1.0,
    "P3Y0M0D": 0.92,
    "P5Y0M0D": 0.86,
}


class RuleBasedValidationRunner(ValidationRunner):
    def __init__(self, *, base_time: datetime | None = None):
        self.base_time = base_time

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
    ) -> ValidationRecord:
        stage = validation_stage
        period_factor = _PERIOD_FACTORS.get(period, 0.88)
        stage_factor = 0.94 if stage == ValidationStage.STAGE_B else 0.9
        family_bias = 1.02 if hypothesis.family == "quality_deterioration" else 0.98

        sharpe = round(1.08 * period_factor * stage_factor * family_bias, 2)
        fitness = round(0.96 * period_factor * stage_factor, 2)
        turnover = round(0.17 if stage == ValidationStage.STAGE_B else 0.15, 2)
        returns = round(0.13 * period_factor * stage_factor, 2)
        drawdown = round(0.07 if stage == ValidationStage.STAGE_B else 0.06, 2)
        grade = "A" if sharpe >= 0.95 else "B"
        checks = [
            "period_window_ok",
            "turnover_ok",
            "drawdown_ok",
            "grade_ok",
        ]
        pass_decision = sharpe >= 0.8 and drawdown <= 0.12
        reasons = ["meets_validation_thresholds"] if pass_decision else ["validation_threshold_breach"]

        return ValidationRecord(
            validation_id=f"validation.{source_run_id}.{candidate.candidate_id}.{stage.value}.{period}",
            candidate_id=candidate.candidate_id,
            hypothesis_id=hypothesis.hypothesis_id,
            blueprint_id=blueprint.blueprint_id,
            source_run_id=source_run_id,
            candidate_source_run_id=candidate_source_run_id,
            validation_stage=stage,
            period=period,
            status=SimulationStatus.SUCCEEDED,
            sharpe=sharpe,
            fitness=fitness,
            turnover=turnover,
            returns=returns,
            drawdown=drawdown,
            checks=checks,
            grade=grade,
            pass_decision=pass_decision,
            reasons=reasons,
            validated_at=self.base_time or datetime.now(timezone.utc),
        )
