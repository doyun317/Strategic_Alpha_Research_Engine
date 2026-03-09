from __future__ import annotations

from pydantic import Field

from strategic_alpha_engine.application.services.interfaces import ValidationRunner
from strategic_alpha_engine.domain.base import EngineModel
from strategic_alpha_engine.domain.enums import ValidationStage
from strategic_alpha_engine.domain.expression_candidate import ExpressionCandidate
from strategic_alpha_engine.domain.hypothesis_spec import HypothesisSpec
from strategic_alpha_engine.domain.signal_blueprint import SignalBlueprint
from strategic_alpha_engine.domain.validation import ValidationRecord


class ValidationOutcome(EngineModel):
    candidate: ExpressionCandidate
    validation: ValidationRecord


class ValidateResult(EngineModel):
    source_run_id: str
    candidate_source_run_id: str
    hypothesis: HypothesisSpec
    blueprint: SignalBlueprint
    outcomes: list[ValidationOutcome] = Field(default_factory=list)
    validated_candidate_ids: list[str] = Field(default_factory=list)
    passed_candidate_ids: list[str] = Field(default_factory=list)
    failed_candidate_ids: list[str] = Field(default_factory=list)


class ValidateWorkflow:
    def __init__(self, validation_runner: ValidationRunner):
        self.validation_runner = validation_runner

    def run(
        self,
        *,
        source_run_id: str,
        candidate_source_run_id: str,
        hypothesis: HypothesisSpec,
        blueprint: SignalBlueprint,
        candidates: list[ExpressionCandidate],
        validation_stage: ValidationStage,
        period: str,
    ) -> ValidateResult:
        outcomes: list[ValidationOutcome] = []
        passed_candidate_ids: list[str] = []
        failed_candidate_ids: list[str] = []

        for candidate in candidates:
            validation = self.validation_runner.validate(
                candidate,
                hypothesis,
                blueprint,
                source_run_id=source_run_id,
                candidate_source_run_id=candidate_source_run_id,
                validation_stage=validation_stage,
                period=period,
            )
            outcomes.append(
                ValidationOutcome(
                    candidate=candidate,
                    validation=validation,
                )
            )
            if validation.pass_decision:
                passed_candidate_ids.append(candidate.candidate_id)
            else:
                failed_candidate_ids.append(candidate.candidate_id)

        return ValidateResult(
            source_run_id=source_run_id,
            candidate_source_run_id=candidate_source_run_id,
            hypothesis=hypothesis,
            blueprint=blueprint,
            outcomes=outcomes,
            validated_candidate_ids=[candidate.candidate_id for candidate in candidates],
            passed_candidate_ids=passed_candidate_ids,
            failed_candidate_ids=failed_candidate_ids,
        )
