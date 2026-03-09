from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from strategic_alpha_engine.application.contracts.simulation import (
    BrainSimulationPollResult,
    BrainSimulationResult,
    BrainSimulationSubmission,
)
from strategic_alpha_engine.domain.base import EngineModel
from strategic_alpha_engine.domain.critique_report import CritiqueReport
from strategic_alpha_engine.domain.evaluation import EvaluationRecord
from strategic_alpha_engine.domain.expression_candidate import ExpressionCandidate
from strategic_alpha_engine.domain.promotion import PromotionDecision
from strategic_alpha_engine.domain.review import HumanReviewDecision
from strategic_alpha_engine.domain.common import ensure_unique_sequence
from strategic_alpha_engine.domain.simulation import SimulationRequest, SimulationRun
from strategic_alpha_engine.domain.enums import ValidationStage
from strategic_alpha_engine.domain.static_validation import StaticValidationReport
from strategic_alpha_engine.domain.validation import ValidationRecord


class CandidateArtifactRecord(EngineModel):
    candidate: ExpressionCandidate
    validation: StaticValidationReport
    critique: CritiqueReport | None = None

    @model_validator(mode="after")
    def validate_lineage(self) -> "CandidateArtifactRecord":
        if self.validation.candidate_id != self.candidate.candidate_id:
            raise ValueError("validation.candidate_id must match candidate.candidate_id")
        if self.validation.blueprint_id != self.candidate.blueprint_id:
            raise ValueError("validation.blueprint_id must match candidate.blueprint_id")
        if self.critique is None:
            return self
        if self.critique.candidate_id != self.candidate.candidate_id:
            raise ValueError("critique.candidate_id must match candidate.candidate_id")
        if self.critique.blueprint_id != self.candidate.blueprint_id:
            raise ValueError("critique.blueprint_id must match candidate.blueprint_id")
        return self


class SimulationArtifactRecord(EngineModel):
    simulation_request: SimulationRequest
    simulation_run: SimulationRun
    submission: BrainSimulationSubmission
    poll_history: list[BrainSimulationPollResult] = Field(default_factory=list)
    result: BrainSimulationResult

    @model_validator(mode="after")
    def validate_lineage(self) -> "SimulationArtifactRecord":
        if self.simulation_run.simulation_request_id != self.simulation_request.simulation_request_id:
            raise ValueError("simulation_run.simulation_request_id must match simulation_request")
        if self.simulation_run.candidate_id != self.simulation_request.candidate_id:
            raise ValueError("simulation_run.candidate_id must match simulation_request.candidate_id")
        if self.submission.simulation_request_id != self.simulation_request.simulation_request_id:
            raise ValueError("submission.simulation_request_id must match simulation_request")
        if self.result.simulation_request_id != self.simulation_request.simulation_request_id:
            raise ValueError("result.simulation_request_id must match simulation_request")
        if self.result.candidate_id != self.simulation_request.candidate_id:
            raise ValueError("result.candidate_id must match simulation_request.candidate_id")
        if self.result.provider_run_id != self.submission.provider_run_id:
            raise ValueError("result.provider_run_id must match submission.provider_run_id")
        if self.simulation_run.provider_run_id != self.submission.provider_run_id:
            raise ValueError("simulation_run.provider_run_id must match submission.provider_run_id")
        for poll in self.poll_history:
            if poll.provider_run_id != self.submission.provider_run_id:
                raise ValueError("poll_history provider_run_id values must match submission.provider_run_id")
        return self


class EvaluationArtifactRecord(EngineModel):
    evaluation: EvaluationRecord
    simulation_run: SimulationRun
    result: BrainSimulationResult

    @model_validator(mode="after")
    def validate_lineage(self) -> "EvaluationArtifactRecord":
        if self.evaluation.candidate_id != self.simulation_run.candidate_id:
            raise ValueError("evaluation.candidate_id must match simulation_run.candidate_id")
        if self.evaluation.simulation_request_id != self.simulation_run.simulation_request_id:
            raise ValueError("evaluation.simulation_request_id must match simulation_run")
        if self.evaluation.simulation_run_id != self.simulation_run.simulation_run_id:
            raise ValueError("evaluation.simulation_run_id must match simulation_run.simulation_run_id")
        if self.result.candidate_id != self.evaluation.candidate_id:
            raise ValueError("result.candidate_id must match evaluation.candidate_id")
        if self.result.simulation_request_id != self.evaluation.simulation_request_id:
            raise ValueError("result.simulation_request_id must match evaluation.simulation_request_id")
        return self


class PromotionArtifactRecord(EngineModel):
    evaluation: EvaluationRecord
    promotion: PromotionDecision

    @model_validator(mode="after")
    def validate_lineage(self) -> "PromotionArtifactRecord":
        if self.promotion.evaluation_id != self.evaluation.evaluation_id:
            raise ValueError("promotion.evaluation_id must match evaluation.evaluation_id")
        if self.promotion.candidate_id != self.evaluation.candidate_id:
            raise ValueError("promotion.candidate_id must match evaluation.candidate_id")
        if self.promotion.hypothesis_id != self.evaluation.hypothesis_id:
            raise ValueError("promotion.hypothesis_id must match evaluation.hypothesis_id")
        if self.promotion.blueprint_id != self.evaluation.blueprint_id:
            raise ValueError("promotion.blueprint_id must match evaluation.blueprint_id")
        if self.promotion.source_run_id != self.evaluation.source_run_id:
            raise ValueError("promotion.source_run_id must match evaluation.source_run_id")
        return self


class ValidationArtifactRecord(EngineModel):
    candidate: ExpressionCandidate
    validation: ValidationRecord

    @model_validator(mode="after")
    def validate_lineage(self) -> "ValidationArtifactRecord":
        if self.validation.candidate_id != self.candidate.candidate_id:
            raise ValueError("validation.candidate_id must match candidate.candidate_id")
        if self.validation.hypothesis_id != self.candidate.hypothesis_id:
            raise ValueError("validation.hypothesis_id must match candidate.hypothesis_id")
        if self.validation.blueprint_id != self.candidate.blueprint_id:
            raise ValueError("validation.blueprint_id must match candidate.blueprint_id")
        return self


class ValidationPromotionArtifactRecord(EngineModel):
    candidate: ExpressionCandidate
    validation_stage: ValidationStage
    requested_periods: list[str] = Field(default_factory=list)
    validation_ids: list[str] = Field(default_factory=list)
    passing_periods: list[str] = Field(default_factory=list)
    failing_periods: list[str] = Field(default_factory=list)
    aggregate_pass_decision: bool
    promotion: PromotionDecision

    @field_validator("requested_periods", "validation_ids", "passing_periods", "failing_periods")
    @classmethod
    def validate_unique_lists(cls, value: list[str], info) -> list[str]:
        return ensure_unique_sequence(value, info.field_name)

    @model_validator(mode="after")
    def validate_lineage(self) -> "ValidationPromotionArtifactRecord":
        if not self.validation_ids:
            raise ValueError("validation_ids must not be empty")
        if self.promotion.candidate_id != self.candidate.candidate_id:
            raise ValueError("promotion.candidate_id must match candidate.candidate_id")
        if self.promotion.hypothesis_id != self.candidate.hypothesis_id:
            raise ValueError("promotion.hypothesis_id must match candidate.hypothesis_id")
        if self.promotion.blueprint_id != self.candidate.blueprint_id:
            raise ValueError("promotion.blueprint_id must match candidate.blueprint_id")
        return self


class SubmissionReadyArtifactRecord(EngineModel):
    candidate: ExpressionCandidate
    robust_promotion: ValidationPromotionArtifactRecord
    submission_promotion: PromotionDecision

    @model_validator(mode="after")
    def validate_lineage(self) -> "SubmissionReadyArtifactRecord":
        if self.robust_promotion.candidate.candidate_id != self.candidate.candidate_id:
            raise ValueError("robust_promotion candidate must match candidate")
        if self.submission_promotion.candidate_id != self.candidate.candidate_id:
            raise ValueError("submission_promotion.candidate_id must match candidate.candidate_id")
        if self.submission_promotion.hypothesis_id != self.candidate.hypothesis_id:
            raise ValueError("submission_promotion.hypothesis_id must match candidate.hypothesis_id")
        if self.submission_promotion.blueprint_id != self.candidate.blueprint_id:
            raise ValueError("submission_promotion.blueprint_id must match candidate.blueprint_id")
        return self


class HumanReviewArtifactRecord(EngineModel):
    submission_ready: SubmissionReadyArtifactRecord
    review_decision: HumanReviewDecision

    @model_validator(mode="after")
    def validate_lineage(self) -> "HumanReviewArtifactRecord":
        candidate = self.submission_ready.candidate
        if self.review_decision.candidate_id != candidate.candidate_id:
            raise ValueError("review_decision.candidate_id must match submission_ready.candidate.candidate_id")
        if self.review_decision.hypothesis_id != candidate.hypothesis_id:
            raise ValueError("review_decision.hypothesis_id must match submission_ready candidate lineage")
        if self.review_decision.blueprint_id != candidate.blueprint_id:
            raise ValueError("review_decision.blueprint_id must match submission_ready candidate lineage")
        if self.review_decision.submission_ready_source_run_id != self.submission_ready.submission_promotion.source_run_id:
            raise ValueError("review_decision.submission_ready_source_run_id must match submission_ready promotion")
        return self
