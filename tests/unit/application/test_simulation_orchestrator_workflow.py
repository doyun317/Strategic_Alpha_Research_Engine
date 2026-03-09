from datetime import datetime, timedelta, timezone

import pytest

from strategic_alpha_engine.application.contracts import (
    BrainSimulationPollResult,
    BrainSimulationSubmission,
)
from strategic_alpha_engine.application.workflows import (
    CandidateEvaluation,
    SimulationExecutionPolicy,
    SimulationOrchestratorWorkflow,
    SynthesizeResult,
)
from strategic_alpha_engine.domain.critique_report import CritiqueIssue, CritiqueReport
from strategic_alpha_engine.domain.enums import SimulationStatus
from strategic_alpha_engine.domain.examples import (
    build_sample_expression_candidate,
    build_sample_hypothesis_spec,
    build_sample_signal_blueprint,
)
from strategic_alpha_engine.domain.static_validation import StaticValidationReport
from strategic_alpha_engine.infrastructure import FakeBrainSimulationClient


def _build_validation(candidate_id: str) -> StaticValidationReport:
    return StaticValidationReport(
        validation_id=f"static.validation.{candidate_id}",
        candidate_id=candidate_id,
        blueprint_id="bp.quality_deterioration.001",
        passes=True,
        checked_operator_count=5,
        checked_field_count=2,
        issues=[],
    )


def _build_critique(candidate_id: str, *, passes: bool) -> CritiqueReport:
    return CritiqueReport(
        critique_id=f"critique.{candidate_id}",
        candidate_id=candidate_id,
        blueprint_id="bp.quality_deterioration.001",
        passes=passes,
        overall_score=0.88 if passes else 0.31,
        structural_quality_score=0.9 if passes else 0.4,
        economic_coherence_score=0.86 if passes else 0.35,
        data_horizon_alignment_score=0.88 if passes else 0.45,
        issues=[]
        if passes
        else [
            CritiqueIssue(
                code="bad_alignment",
                severity="high",
                message="Signal intent does not align with the blueprint thesis.",
                suggestion="Rework the expression before simulation.",
            )
        ],
        repair_suggestions=[] if passes else ["Drop this candidate from simulation."],
        tags=["quality"],
    )


def _build_synthesize_result() -> SynthesizeResult:
    accepted_candidate = build_sample_expression_candidate().model_copy(
        update={"candidate_id": "cand.accepted.001"}
    )
    rejected_candidate = build_sample_expression_candidate().model_copy(
        update={"candidate_id": "cand.rejected.001"}
    )
    accepted_evaluation = CandidateEvaluation(
        candidate=accepted_candidate,
        validation=_build_validation(accepted_candidate.candidate_id),
        critique=_build_critique(accepted_candidate.candidate_id, passes=True),
    )
    rejected_evaluation = CandidateEvaluation(
        candidate=rejected_candidate,
        validation=_build_validation(rejected_candidate.candidate_id),
        critique=_build_critique(rejected_candidate.candidate_id, passes=False),
    )
    return SynthesizeResult(
        hypothesis=build_sample_hypothesis_spec(),
        blueprint=build_sample_signal_blueprint(),
        evaluations=[accepted_evaluation, rejected_evaluation],
        accepted_candidate_ids=[accepted_candidate.candidate_id],
        rejected_candidate_ids=[rejected_candidate.candidate_id],
    )


def test_simulation_orchestrator_runs_only_accepted_candidates():
    workflow = SimulationOrchestratorWorkflow(
        brain_client=FakeBrainSimulationClient(),
        max_polls=3,
    )

    result = workflow.run(
        synthesize_result=_build_synthesize_result(),
        policy=SimulationExecutionPolicy(),
    )

    assert result.simulated_candidate_ids == ["cand.accepted.001"]
    assert result.skipped_candidate_ids == ["cand.rejected.001"]
    assert len(result.executions) == 1
    assert result.executions[0].simulation_request.candidate_id == "cand.accepted.001"
    assert result.executions[0].simulation_run.status == SimulationStatus.SUCCEEDED
    assert [poll.status for poll in result.executions[0].poll_history] == [
        SimulationStatus.SUBMITTED,
        SimulationStatus.RUNNING,
        SimulationStatus.SUCCEEDED,
    ]


def test_simulation_orchestrator_marks_timeout_when_terminal_status_is_never_reached():
    class NeverTerminalBrainClient:
        def __init__(self):
            self.accepted_at = datetime(2026, 1, 15, 14, 30, tzinfo=timezone.utc)

        def submit(self, request):
            return BrainSimulationSubmission(
                simulation_request_id=request.simulation_request_id,
                provider_run_id="brain.never_terminal.001",
                status=SimulationStatus.SUBMITTED,
                accepted_at=self.accepted_at,
            )

        def poll(self, provider_run_id):
            return BrainSimulationPollResult(
                provider_run_id=provider_run_id,
                status=SimulationStatus.RUNNING,
                observed_at=self.accepted_at + timedelta(minutes=1),
            )

        def fetch_result(self, provider_run_id):
            raise AssertionError("fetch_result must not be called before a terminal poll result exists")

    workflow = SimulationOrchestratorWorkflow(
        brain_client=NeverTerminalBrainClient(),
        max_polls=2,
    )

    result = workflow.run(
        synthesize_result=_build_synthesize_result(),
        policy=SimulationExecutionPolicy(),
    )

    assert result.executions[0].simulation_run.status == SimulationStatus.TIMED_OUT
    assert result.executions[0].result.status == SimulationStatus.TIMED_OUT
    assert len(result.executions[0].poll_history) == 2


def test_simulation_orchestrator_rejects_non_passing_candidates_in_accept_list():
    synthesize_result = _build_synthesize_result().model_copy(
        update={"accepted_candidate_ids": ["cand.rejected.001"]}
    )
    workflow = SimulationOrchestratorWorkflow(
        brain_client=FakeBrainSimulationClient(),
        max_polls=3,
    )

    with pytest.raises(
        ValueError,
        match="accepted_candidate_ids must only include candidates with a passing critique",
    ):
        workflow.run(
            synthesize_result=synthesize_result,
            policy=SimulationExecutionPolicy(),
        )
