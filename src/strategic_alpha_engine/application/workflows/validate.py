from __future__ import annotations

from collections import defaultdict

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


class CandidateValidationMatrixRow(EngineModel):
    candidate_id: str
    passing_periods: list[str] = Field(default_factory=list)
    failing_periods: list[str] = Field(default_factory=list)
    grades_by_period: dict[str, str] = Field(default_factory=dict)
    pass_count: int = 0
    fail_count: int = 0
    aggregate_pass_decision: bool
    reasons: list[str] = Field(default_factory=list)


class ValidationMatrixSummary(EngineModel):
    source_run_id: str
    validation_stage: ValidationStage
    requested_periods: list[str] = Field(default_factory=list)
    required_passing_periods: int
    total_candidates: int
    passed_candidate_count: int
    failed_candidate_count: int
    rows: list[CandidateValidationMatrixRow] = Field(default_factory=list)


class MultiPeriodValidateResult(EngineModel):
    source_run_id: str
    candidate_source_run_id: str
    hypothesis: HypothesisSpec
    blueprint: SignalBlueprint
    validation_stage: ValidationStage
    requested_periods: list[str] = Field(default_factory=list)
    period_results: list[ValidateResult] = Field(default_factory=list)
    validation_matrix: ValidationMatrixSummary
    validated_candidate_ids: list[str] = Field(default_factory=list)
    passed_candidate_ids: list[str] = Field(default_factory=list)
    failed_candidate_ids: list[str] = Field(default_factory=list)


def build_validation_matrix(
    validation_records: list[ValidationRecord],
    *,
    source_run_id: str,
    validation_stage: ValidationStage,
    requested_periods: list[str],
    minimum_passing_periods: int = 2,
) -> ValidationMatrixSummary:
    records_by_candidate: dict[str, list[ValidationRecord]] = defaultdict(list)
    for record in validation_records:
        records_by_candidate[record.candidate_id].append(record)

    required_passing_periods = min(max(minimum_passing_periods, 1), len(requested_periods))
    rows: list[CandidateValidationMatrixRow] = []
    passed_candidate_count = 0

    for candidate_id in sorted(records_by_candidate):
        records = sorted(records_by_candidate[candidate_id], key=lambda record: record.period)
        passing_periods = [record.period for record in records if record.pass_decision]
        failing_periods = [record.period for record in records if not record.pass_decision]
        grades_by_period = {
            record.period: record.grade
            for record in records
        }
        aggregate_pass_decision = len(passing_periods) >= required_passing_periods and not any(
            grade.upper() in {"D", "F"}
            for grade in grades_by_period.values()
        )
        if aggregate_pass_decision:
            reasons = [f"passed_{len(passing_periods)}_of_{len(requested_periods)}_periods"]
            passed_candidate_count += 1
        else:
            reasons = [f"passed_{len(passing_periods)}_of_{len(requested_periods)}_periods"]

        rows.append(
            CandidateValidationMatrixRow(
                candidate_id=candidate_id,
                passing_periods=passing_periods,
                failing_periods=failing_periods,
                grades_by_period=grades_by_period,
                pass_count=len(passing_periods),
                fail_count=len(failing_periods),
                aggregate_pass_decision=aggregate_pass_decision,
                reasons=reasons,
            )
        )

    return ValidationMatrixSummary(
        source_run_id=source_run_id,
        validation_stage=validation_stage,
        requested_periods=requested_periods,
        required_passing_periods=required_passing_periods,
        total_candidates=len(rows),
        passed_candidate_count=passed_candidate_count,
        failed_candidate_count=len(rows) - passed_candidate_count,
        rows=rows,
    )


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


class MultiPeriodValidateWorkflow:
    def __init__(
        self,
        validate_workflow: ValidateWorkflow,
        *,
        minimum_passing_periods: int = 2,
    ):
        self.validate_workflow = validate_workflow
        self.minimum_passing_periods = minimum_passing_periods

    def run(
        self,
        *,
        source_run_id: str,
        candidate_source_run_id: str,
        hypothesis: HypothesisSpec,
        blueprint: SignalBlueprint,
        candidates: list[ExpressionCandidate],
        validation_stage: ValidationStage,
        periods: list[str],
    ) -> MultiPeriodValidateResult:
        if not periods:
            raise ValueError("periods must not be empty")

        period_results: list[ValidateResult] = []
        all_validation_records: list[ValidationRecord] = []
        for period in periods:
            result = self.validate_workflow.run(
                source_run_id=source_run_id,
                candidate_source_run_id=candidate_source_run_id,
                hypothesis=hypothesis,
                blueprint=blueprint,
                candidates=candidates,
                validation_stage=validation_stage,
                period=period,
            )
            period_results.append(result)
            all_validation_records.extend(
                outcome.validation
                for outcome in result.outcomes
            )

        validation_matrix = build_validation_matrix(
            all_validation_records,
            source_run_id=source_run_id,
            validation_stage=validation_stage,
            requested_periods=periods,
            minimum_passing_periods=self.minimum_passing_periods,
        )
        passed_candidate_ids = [
            row.candidate_id
            for row in validation_matrix.rows
            if row.aggregate_pass_decision
        ]
        failed_candidate_ids = [
            row.candidate_id
            for row in validation_matrix.rows
            if not row.aggregate_pass_decision
        ]

        return MultiPeriodValidateResult(
            source_run_id=source_run_id,
            candidate_source_run_id=candidate_source_run_id,
            hypothesis=hypothesis,
            blueprint=blueprint,
            validation_stage=validation_stage,
            requested_periods=periods,
            period_results=period_results,
            validation_matrix=validation_matrix,
            validated_candidate_ids=[candidate.candidate_id for candidate in candidates],
            passed_candidate_ids=passed_candidate_ids,
            failed_candidate_ids=failed_candidate_ids,
        )
