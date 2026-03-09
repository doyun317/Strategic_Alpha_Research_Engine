import pytest

from strategic_alpha_engine.domain.enums import SimulationStatus
from strategic_alpha_engine.domain.examples import build_sample_simulation_request
from strategic_alpha_engine.infrastructure import FakeBrainSimulationClient


def test_fake_brain_simulation_client_submit_poll_and_fetch_result():
    client = FakeBrainSimulationClient()
    request = build_sample_simulation_request()

    submission = client.submit(request)
    first_poll = client.poll(submission.provider_run_id)
    second_poll = client.poll(submission.provider_run_id)
    third_poll = client.poll(submission.provider_run_id)
    result = client.fetch_result(submission.provider_run_id)

    assert submission.status == SimulationStatus.SUBMITTED
    assert first_poll.status == SimulationStatus.SUBMITTED
    assert second_poll.status == SimulationStatus.RUNNING
    assert third_poll.status == SimulationStatus.SUCCEEDED
    assert result.status == SimulationStatus.SUCCEEDED
    assert result.candidate_id == request.candidate_id
    assert result.sharpe is not None


def test_fake_brain_simulation_client_supports_failure_terminal_status():
    client = FakeBrainSimulationClient(terminal_status=SimulationStatus.FAILED)
    request = build_sample_simulation_request()

    submission = client.submit(request)
    client.poll(submission.provider_run_id)
    client.poll(submission.provider_run_id)
    client.poll(submission.provider_run_id)
    result = client.fetch_result(submission.provider_run_id)

    assert result.status == SimulationStatus.FAILED
    assert result.sharpe is None
    assert result.grade is None


def test_fake_brain_simulation_client_rejects_fetch_before_terminal_status():
    client = FakeBrainSimulationClient()
    request = build_sample_simulation_request()

    submission = client.submit(request)

    with pytest.raises(ValueError, match="cannot fetch result before fake brain run reaches a terminal status"):
        client.fetch_result(submission.provider_run_id)
