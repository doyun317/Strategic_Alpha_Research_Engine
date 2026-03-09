from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from strategic_alpha_engine.domain import build_sample_simulation_request, build_sample_simulation_run
from strategic_alpha_engine.domain.enums import SimulationStatus
from strategic_alpha_engine.domain.simulation import SimulationRequest, SimulationRun


def test_simulation_request_builds_valid_sample():
    request = build_sample_simulation_request()

    assert request.candidate_id == "cand.quality_deterioration.001"
    assert request.test_period == "P1Y0M0D"


def test_simulation_request_is_immutable():
    request = build_sample_simulation_request()

    with pytest.raises(ValidationError):
        request.delay = 2


def test_simulation_request_rejects_invalid_test_period():
    payload = build_sample_simulation_request().model_dump()
    payload["test_period"] = "1Y"

    with pytest.raises(ValidationError):
        SimulationRequest(**payload)


def test_simulation_run_builds_valid_sample():
    run = build_sample_simulation_run()

    assert run.status == SimulationStatus.SUCCEEDED
    assert run.provider_run_id == "brain.run.quality_deterioration.001"
    assert run.completed_at >= run.submitted_at


def test_simulation_run_from_request_copies_request_snapshot():
    request = build_sample_simulation_request()

    run = SimulationRun.from_request(
        simulation_run_id="simrun.quality_deterioration.snapshot.001",
        request=request,
    )

    assert run.simulation_request_id == request.simulation_request_id
    assert run.region == request.region
    assert run.test_period == request.test_period
    assert run.status == SimulationStatus.PENDING


def test_simulation_run_submit_and_complete_return_new_instances():
    request = build_sample_simulation_request()
    pending_run = SimulationRun.from_request("simrun.quality_deterioration.lifecycle.001", request)
    submitted_at = datetime(2026, 1, 15, 14, 30, tzinfo=timezone.utc)
    completed_at = datetime(2026, 1, 15, 14, 42, tzinfo=timezone.utc)

    submitted_run = pending_run.mark_submitted(
        provider_run_id="brain.run.lifecycle.001",
        submitted_at=submitted_at,
    )
    completed_run = submitted_run.mark_succeeded(completed_at=completed_at)

    assert pending_run.status == SimulationStatus.PENDING
    assert submitted_run.status == SimulationStatus.SUBMITTED
    assert completed_run.status == SimulationStatus.SUCCEEDED
    assert submitted_run.provider_run_id == "brain.run.lifecycle.001"
    assert completed_run.completed_at == completed_at


def test_simulation_run_rejects_invalid_transition():
    pending_run = SimulationRun.from_request(
        simulation_run_id="simrun.quality_deterioration.invalid.001",
        request=build_sample_simulation_request(),
    )

    with pytest.raises(ValueError, match="cannot transition simulation run from pending to succeeded"):
        pending_run.mark_succeeded(completed_at=datetime(2026, 1, 15, 14, 42, tzinfo=timezone.utc))


def test_simulation_run_rejects_completed_at_before_submitted_at():
    payload = build_sample_simulation_run().model_dump(mode="python")
    payload["status"] = SimulationStatus.SUCCEEDED
    payload["submitted_at"] = datetime(2026, 1, 15, 14, 42, tzinfo=timezone.utc)
    payload["completed_at"] = datetime(2026, 1, 15, 14, 30, tzinfo=timezone.utc)

    with pytest.raises(ValidationError, match="completed_at must be greater than or equal to submitted_at"):
        SimulationRun(**payload)


def test_simulation_run_rejects_naive_timestamps():
    payload = build_sample_simulation_run().model_dump(mode="python")
    payload["submitted_at"] = datetime(2026, 1, 15, 14, 30)

    with pytest.raises(ValidationError, match="submitted_at must be timezone-aware"):
        SimulationRun(**payload)
