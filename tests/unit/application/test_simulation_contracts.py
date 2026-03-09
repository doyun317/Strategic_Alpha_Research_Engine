from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from strategic_alpha_engine.application.contracts import (
    BrainSimulationPollResult,
    BrainSimulationResult,
    BrainSimulationSubmission,
)
from strategic_alpha_engine.domain.enums import SimulationStatus
from strategic_alpha_engine.domain.examples import build_sample_simulation_request


def test_brain_simulation_submission_accepts_active_statuses():
    submission = BrainSimulationSubmission(
        simulation_request_id=build_sample_simulation_request().simulation_request_id,
        provider_run_id="brain.run.contract.001",
        status=SimulationStatus.SUBMITTED,
        accepted_at=datetime(2026, 1, 15, 14, 30, tzinfo=timezone.utc),
    )

    assert submission.status == SimulationStatus.SUBMITTED


def test_brain_simulation_poll_rejects_pending_status():
    with pytest.raises(ValidationError, match="must not be pending"):
        BrainSimulationPollResult(
            provider_run_id="brain.run.contract.002",
            status=SimulationStatus.PENDING,
            observed_at=datetime(2026, 1, 15, 14, 31, tzinfo=timezone.utc),
        )


def test_brain_simulation_result_requires_metrics_for_success():
    request = build_sample_simulation_request()

    with pytest.raises(ValidationError, match="must include all core metrics"):
        BrainSimulationResult(
            simulation_request_id=request.simulation_request_id,
            candidate_id=request.candidate_id,
            provider_run_id="brain.run.contract.003",
            status=SimulationStatus.SUCCEEDED,
            completed_at=datetime(2026, 1, 15, 14, 42, tzinfo=timezone.utc),
        )
