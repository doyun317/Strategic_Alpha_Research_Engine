from __future__ import annotations

from pydantic import Field

from strategic_alpha_engine.application.services.interfaces import (
    CandidateSynthesizer,
    StaticValidator,
    StrategicCritic,
)
from strategic_alpha_engine.domain.base import EngineModel
from strategic_alpha_engine.domain.critique_report import CritiqueReport
from strategic_alpha_engine.domain.expression_candidate import ExpressionCandidate
from strategic_alpha_engine.domain.hypothesis_spec import HypothesisSpec
from strategic_alpha_engine.domain.signal_blueprint import SignalBlueprint
from strategic_alpha_engine.domain.static_validation import StaticValidationReport


class CandidateEvaluation(EngineModel):
    candidate: ExpressionCandidate
    validation: StaticValidationReport
    critique: CritiqueReport | None = None


class SynthesizeResult(EngineModel):
    hypothesis: HypothesisSpec
    blueprint: SignalBlueprint
    evaluations: list[CandidateEvaluation] = Field(default_factory=list)
    accepted_candidate_ids: list[str] = Field(default_factory=list)
    rejected_candidate_ids: list[str] = Field(default_factory=list)


class SynthesizeWorkflow:
    def __init__(
        self,
        candidate_synthesizer: CandidateSynthesizer,
        static_validator: StaticValidator,
        strategic_critic: StrategicCritic,
    ):
        self.candidate_synthesizer = candidate_synthesizer
        self.static_validator = static_validator
        self.strategic_critic = strategic_critic

    def run(self, hypothesis: HypothesisSpec, blueprint: SignalBlueprint) -> SynthesizeResult:
        if blueprint.hypothesis_id != hypothesis.hypothesis_id:
            raise ValueError("blueprint.hypothesis_id must match hypothesis.hypothesis_id")

        candidates = self.candidate_synthesizer.synthesize(blueprint)
        evaluations: list[CandidateEvaluation] = []
        accepted: list[str] = []
        rejected: list[str] = []

        for candidate in candidates:
            validation = self.static_validator.validate(blueprint, candidate)
            if not validation.passes:
                evaluations.append(
                    CandidateEvaluation(
                        candidate=candidate,
                        validation=validation,
                    )
                )
                rejected.append(candidate.candidate_id)
                continue

            critique = self.strategic_critic.critique(hypothesis, blueprint, candidate)
            evaluations.append(
                CandidateEvaluation(
                    candidate=candidate,
                    validation=validation,
                    critique=critique,
                )
            )
            if critique.passes:
                accepted.append(candidate.candidate_id)
            else:
                rejected.append(candidate.candidate_id)

        return SynthesizeResult(
            hypothesis=hypothesis,
            blueprint=blueprint,
            evaluations=evaluations,
            accepted_candidate_ids=accepted,
            rejected_candidate_ids=rejected,
        )
