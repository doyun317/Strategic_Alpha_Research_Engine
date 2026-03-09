from __future__ import annotations

from pydantic import Field, model_validator

from strategic_alpha_engine.application.contracts.simulation import (
    BrainSimulationPollResult,
    BrainSimulationResult,
    BrainSimulationSubmission,
)
from strategic_alpha_engine.domain.base import EngineModel
from strategic_alpha_engine.domain.critique_report import CritiqueReport
from strategic_alpha_engine.domain.expression_candidate import ExpressionCandidate
from strategic_alpha_engine.domain.simulation import SimulationRequest, SimulationRun
from strategic_alpha_engine.domain.static_validation import StaticValidationReport


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
