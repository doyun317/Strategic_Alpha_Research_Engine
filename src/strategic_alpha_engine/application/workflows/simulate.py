from __future__ import annotations

from pydantic import Field

from strategic_alpha_engine.application.contracts.simulation import (
    BrainSimulationPollResult,
    BrainSimulationResult,
    BrainSimulationSubmission,
)
from strategic_alpha_engine.application.services.interfaces import BrainSimulationClient
from strategic_alpha_engine.application.workflows.synthesize import CandidateEvaluation, SynthesizeResult
from strategic_alpha_engine.domain.base import EngineModel
from strategic_alpha_engine.domain.critique_report import CritiqueReport
from strategic_alpha_engine.domain.enums import SimulationStatus
from strategic_alpha_engine.domain.expression_candidate import ExpressionCandidate
from strategic_alpha_engine.domain.hypothesis_spec import HypothesisSpec
from strategic_alpha_engine.domain.signal_blueprint import SignalBlueprint
from strategic_alpha_engine.domain.simulation import SimulationRequest, SimulationRun

_TERMINAL_STATUSES = {
    SimulationStatus.SUCCEEDED,
    SimulationStatus.FAILED,
    SimulationStatus.TIMED_OUT,
}


class SimulationExecutionPolicy(EngineModel):
    region: str = Field(default="USA", min_length=2, max_length=16)
    universe: str = Field(default="TOP3000", min_length=2, max_length=32)
    delay: int = Field(default=1, ge=0, le=10)
    neutralization: str = Field(default="subindustry", min_length=2, max_length=64)
    test_period: str = Field(default="P1Y0M0D", min_length=2, max_length=32)


class SimulationCandidateExecution(EngineModel):
    candidate: ExpressionCandidate
    critique: CritiqueReport
    simulation_request: SimulationRequest
    simulation_run: SimulationRun
    submission: BrainSimulationSubmission
    poll_history: list[BrainSimulationPollResult] = Field(default_factory=list)
    result: BrainSimulationResult


class SimulationOrchestratorResult(EngineModel):
    hypothesis: HypothesisSpec
    blueprint: SignalBlueprint
    policy: SimulationExecutionPolicy
    executions: list[SimulationCandidateExecution] = Field(default_factory=list)
    simulated_candidate_ids: list[str] = Field(default_factory=list)
    skipped_candidate_ids: list[str] = Field(default_factory=list)


class SimulationOrchestratorWorkflow:
    def __init__(
        self,
        brain_client: BrainSimulationClient,
        *,
        max_polls: int = 3,
    ):
        if max_polls < 1:
            raise ValueError("max_polls must be at least 1")
        self.brain_client = brain_client
        self.max_polls = max_polls

    def run(
        self,
        synthesize_result: SynthesizeResult,
        policy: SimulationExecutionPolicy,
    ) -> SimulationOrchestratorResult:
        accepted_evaluations = self._select_accepted_evaluations(synthesize_result)
        accepted_candidate_ids = {evaluation.candidate.candidate_id for evaluation in accepted_evaluations}
        executions: list[SimulationCandidateExecution] = []
        simulated_candidate_ids: list[str] = []
        skipped_candidate_ids = [
            evaluation.candidate.candidate_id
            for evaluation in synthesize_result.evaluations
            if evaluation.candidate.candidate_id not in accepted_candidate_ids
        ]

        for index, evaluation in enumerate(accepted_evaluations, start=1):
            execution = self._execute_candidate(
                hypothesis=synthesize_result.hypothesis,
                blueprint=synthesize_result.blueprint,
                evaluation=evaluation,
                policy=policy,
                ordinal=index,
            )
            executions.append(execution)
            simulated_candidate_ids.append(evaluation.candidate.candidate_id)

        return SimulationOrchestratorResult(
            hypothesis=synthesize_result.hypothesis,
            blueprint=synthesize_result.blueprint,
            policy=policy,
            executions=executions,
            simulated_candidate_ids=simulated_candidate_ids,
            skipped_candidate_ids=skipped_candidate_ids,
        )

    def _select_accepted_evaluations(
        self,
        synthesize_result: SynthesizeResult,
    ) -> list[CandidateEvaluation]:
        accepted_ids = set(synthesize_result.accepted_candidate_ids)
        evaluations_by_candidate_id: dict[str, CandidateEvaluation] = {}

        for evaluation in synthesize_result.evaluations:
            candidate_id = evaluation.candidate.candidate_id
            if candidate_id in evaluations_by_candidate_id:
                raise ValueError("synthesize_result must not contain duplicate candidate evaluations")
            evaluations_by_candidate_id[candidate_id] = evaluation

        unknown_candidate_ids = accepted_ids - set(evaluations_by_candidate_id)
        if unknown_candidate_ids:
            unknown = ", ".join(sorted(unknown_candidate_ids))
            raise ValueError(f"accepted_candidate_ids reference unknown candidates: {unknown}")

        accepted_evaluations: list[CandidateEvaluation] = []
        for evaluation in synthesize_result.evaluations:
            candidate_id = evaluation.candidate.candidate_id
            if candidate_id not in accepted_ids:
                continue
            if evaluation.critique is None or not evaluation.critique.passes:
                raise ValueError(
                    "accepted_candidate_ids must only include candidates with a passing critique"
                )
            accepted_evaluations.append(evaluation)
        return accepted_evaluations

    def _execute_candidate(
        self,
        *,
        hypothesis: HypothesisSpec,
        blueprint: SignalBlueprint,
        evaluation: CandidateEvaluation,
        policy: SimulationExecutionPolicy,
        ordinal: int,
    ) -> SimulationCandidateExecution:
        request = SimulationRequest(
            simulation_request_id=self._build_simulation_request_id(evaluation.candidate, ordinal),
            candidate_id=evaluation.candidate.candidate_id,
            hypothesis_id=hypothesis.hypothesis_id,
            blueprint_id=blueprint.blueprint_id,
            expression=evaluation.candidate.expression,
            region=policy.region,
            universe=policy.universe,
            delay=policy.delay,
            neutralization=policy.neutralization,
            test_period=policy.test_period,
        )
        submission = self.brain_client.submit(request)
        self._validate_submission_matches_request(request, submission)

        run = SimulationRun.from_request(
            simulation_run_id=self._build_simulation_run_id(evaluation.candidate, ordinal),
            request=request,
        ).mark_submitted(
            provider_run_id=submission.provider_run_id,
            submitted_at=submission.accepted_at,
        )

        poll_history: list[BrainSimulationPollResult] = []
        result: BrainSimulationResult | None = None

        for _ in range(self.max_polls):
            poll = self.brain_client.poll(submission.provider_run_id)
            self._validate_poll_matches_submission(submission, poll)
            poll_history.append(poll)

            if poll.status == SimulationStatus.RUNNING and run.status == SimulationStatus.SUBMITTED:
                run = run.mark_running()

            if poll.status in _TERMINAL_STATUSES:
                result = self.brain_client.fetch_result(submission.provider_run_id)
                self._validate_result_matches_request(request, submission, poll, result)
                run = self._apply_result_to_run(run, result)
                break

        if result is None:
            timeout_at = poll_history[-1].observed_at
            result = BrainSimulationResult(
                simulation_request_id=request.simulation_request_id,
                candidate_id=request.candidate_id,
                provider_run_id=submission.provider_run_id,
                status=SimulationStatus.TIMED_OUT,
                completed_at=timeout_at,
                raw_response={
                    "provider": "simulation_orchestrator",
                    "reason": "max_polls_exceeded",
                    "provider_run_id": submission.provider_run_id,
                },
            )
            run = run.mark_timed_out(timeout_at)

        return SimulationCandidateExecution(
            candidate=evaluation.candidate,
            critique=evaluation.critique,
            simulation_request=request,
            simulation_run=run,
            submission=submission,
            poll_history=poll_history,
            result=result,
        )

    def _build_simulation_request_id(self, candidate: ExpressionCandidate, ordinal: int) -> str:
        return f"simreq.{candidate.candidate_id}.{ordinal:03d}"

    def _build_simulation_run_id(self, candidate: ExpressionCandidate, ordinal: int) -> str:
        return f"simrun.{candidate.candidate_id}.{ordinal:03d}"

    def _validate_submission_matches_request(
        self,
        request: SimulationRequest,
        submission: BrainSimulationSubmission,
    ) -> None:
        if submission.simulation_request_id != request.simulation_request_id:
            raise ValueError("Brain submission must reference the originating simulation_request_id")

    def _validate_poll_matches_submission(
        self,
        submission: BrainSimulationSubmission,
        poll: BrainSimulationPollResult,
    ) -> None:
        if poll.provider_run_id != submission.provider_run_id:
            raise ValueError("Brain poll result must reference the originating provider_run_id")

    def _validate_result_matches_request(
        self,
        request: SimulationRequest,
        submission: BrainSimulationSubmission,
        poll: BrainSimulationPollResult,
        result: BrainSimulationResult,
    ) -> None:
        if result.simulation_request_id != request.simulation_request_id:
            raise ValueError("Brain simulation result must reference the originating simulation_request_id")
        if result.candidate_id != request.candidate_id:
            raise ValueError("Brain simulation result must reference the originating candidate_id")
        if result.provider_run_id != submission.provider_run_id:
            raise ValueError("Brain simulation result must reference the originating provider_run_id")
        if result.status != poll.status:
            raise ValueError("Brain simulation result status must match the last terminal poll status")

    def _apply_result_to_run(
        self,
        run: SimulationRun,
        result: BrainSimulationResult,
    ) -> SimulationRun:
        if result.status == SimulationStatus.SUCCEEDED:
            return run.mark_succeeded(result.completed_at)
        if result.status == SimulationStatus.FAILED:
            return run.mark_failed(result.completed_at)
        if result.status == SimulationStatus.TIMED_OUT:
            return run.mark_timed_out(result.completed_at)
        raise ValueError(f"unsupported terminal simulation status: {result.status}")
