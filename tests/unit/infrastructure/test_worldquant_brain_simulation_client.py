from __future__ import annotations

from collections import deque
from datetime import datetime, timezone

import pytest

from strategic_alpha_engine.config import BrainSettings
from strategic_alpha_engine.domain.enums import SimulationStatus
from strategic_alpha_engine.domain.examples import build_sample_simulation_request
from strategic_alpha_engine.infrastructure.brain import WorldQuantBrainSimulationClient


class _FakeResponse:
    def __init__(self, status_code: int, *, headers: dict[str, str] | None = None, json_payload=None, text: str = ""):
        self.status_code = status_code
        self.headers = headers or {}
        self._json_payload = json_payload
        self.text = text or (
            "" if json_payload is None else str(json_payload)
        )

    def json(self):
        if self._json_payload is None:
            raise ValueError("no json payload configured")
        return self._json_payload


class _FakeSession:
    def __init__(self, *, auth_responses: list[_FakeResponse], request_responses: list[_FakeResponse]):
        self.auth = None
        self.headers: dict[str, str] = {}
        self.auth_responses = deque(auth_responses)
        self.request_responses = deque(request_responses)
        self.auth_calls: list[tuple[str, float | None]] = []
        self.request_calls: list[tuple[str, str, dict | None, float | None]] = []

    def post(self, url: str, timeout: float | None = None):
        self.auth_calls.append((url, timeout))
        return self.auth_responses.popleft()

    def request(self, method: str, url: str, json=None, timeout: float | None = None):
        self.request_calls.append((method, url, json, timeout))
        return self.request_responses.popleft()


def _build_settings() -> BrainSettings:
    return BrainSettings(
        base_url="https://api.worldquantbrain.com",
        username="tester@example.com",
        password="secret-pass",
        submit_timeout_seconds=30.0,
        poll_interval_seconds=15.0,
        max_polls=20,
    )


def test_worldquant_brain_client_submit_poll_and_fetch_result():
    session = _FakeSession(
        auth_responses=[_FakeResponse(201)],
        request_responses=[
            _FakeResponse(201, headers={"Location": "/simulations/progress/123"}),
            _FakeResponse(200, json_payload={"status": "PENDING"}),
            _FakeResponse(200, json_payload={"status": "RUNNING"}),
            _FakeResponse(200, json_payload={"status": "COMPLETE", "alpha": "alpha-123"}),
            _FakeResponse(
                200,
                json_payload={
                    "id": "alpha-123",
                    "is": {
                        "sharpe": 1.32,
                        "fitness": 0.84,
                        "turnover": 0.27,
                        "margin": 0.05,
                        "checks": [{"name": "PROD_CORRELATION"}],
                    },
                },
            ),
        ],
    )
    monotonic_values = iter([0.0, 0.0, 0.0, 16.0, 16.0, 32.0, 32.0])
    client = WorldQuantBrainSimulationClient(
        _build_settings(),
        session=session,
        sleep=lambda _: None,
        now_fn=lambda: datetime(2026, 3, 9, 8, 30, tzinfo=timezone.utc),
        monotonic_fn=lambda: next(monotonic_values),
    )
    request = build_sample_simulation_request()

    submission = client.submit(request)
    first_poll = client.poll(submission.provider_run_id)
    second_poll = client.poll(submission.provider_run_id)
    third_poll = client.poll(submission.provider_run_id)
    result = client.fetch_result(submission.provider_run_id)

    submit_payload = session.request_calls[0][2]
    assert submission.provider_run_id == "https://api.worldquantbrain.com/simulations/progress/123"
    assert submit_payload["settings"]["neutralization"] == "SUBINDUSTRY"
    assert first_poll.status == SimulationStatus.SUBMITTED
    assert second_poll.status == SimulationStatus.RUNNING
    assert third_poll.status == SimulationStatus.SUCCEEDED
    assert result.status == SimulationStatus.SUCCEEDED
    assert result.candidate_id == request.candidate_id
    assert result.returns == 0.05
    assert "PROD_CORRELATION" in result.checks
    assert "drawdown_missing_defaulted" in result.checks
    assert result.grade == "B"


def test_worldquant_brain_client_reauthenticates_on_unauthorized_submit():
    session = _FakeSession(
        auth_responses=[_FakeResponse(201), _FakeResponse(201)],
        request_responses=[
            _FakeResponse(401, text="expired"),
            _FakeResponse(201, headers={"Location": "/simulations/progress/reauth"}),
        ],
    )
    client = WorldQuantBrainSimulationClient(
        _build_settings(),
        session=session,
        sleep=lambda _: None,
        now_fn=lambda: datetime(2026, 3, 9, 8, 31, tzinfo=timezone.utc),
        monotonic_fn=lambda: 0.0,
    )

    submission = client.submit(build_sample_simulation_request())

    assert submission.provider_run_id.endswith("/simulations/progress/reauth")
    assert len(session.auth_calls) == 2


def test_worldquant_brain_client_handles_failed_progress_result():
    session = _FakeSession(
        auth_responses=[_FakeResponse(201)],
        request_responses=[
            _FakeResponse(201, headers={"Location": "/simulations/progress/fail"}),
            _FakeResponse(200, json_payload={"status": "ERROR", "message": "SIMULATION_LIMIT_EXCEEDED"}),
        ],
    )
    client = WorldQuantBrainSimulationClient(
        _build_settings(),
        session=session,
        sleep=lambda _: None,
        now_fn=lambda: datetime(2026, 3, 9, 8, 32, tzinfo=timezone.utc),
        monotonic_fn=lambda: 0.0,
    )

    submission = client.submit(build_sample_simulation_request())
    poll = client.poll(submission.provider_run_id)
    result = client.fetch_result(submission.provider_run_id)

    assert poll.status == SimulationStatus.FAILED
    assert result.status == SimulationStatus.FAILED
    assert result.sharpe is None


def test_worldquant_brain_client_waits_on_rate_limit_retry_after():
    slept: list[float] = []
    session = _FakeSession(
        auth_responses=[_FakeResponse(201)],
        request_responses=[
            _FakeResponse(201, headers={"Location": "/simulations/progress/rate-limit"}),
            _FakeResponse(429, headers={"Retry-After": "2.5"}, text="too many requests"),
            _FakeResponse(200, json_payload={"status": "RUNNING"}),
        ],
    )
    client = WorldQuantBrainSimulationClient(
        _build_settings(),
        session=session,
        sleep=lambda seconds: slept.append(seconds),
        now_fn=lambda: datetime(2026, 3, 9, 8, 33, tzinfo=timezone.utc),
        monotonic_fn=lambda: 0.0,
    )

    submission = client.submit(build_sample_simulation_request())
    poll = client.poll(submission.provider_run_id)

    assert poll.status == SimulationStatus.RUNNING
    assert slept == [2.5]


def test_worldquant_brain_client_maps_progress_only_payload_to_running():
    session = _FakeSession(
        auth_responses=[_FakeResponse(201)],
        request_responses=[
            _FakeResponse(201, headers={"Location": "/simulations/progress/progress-only"}),
            _FakeResponse(200, json_payload={"progress": 0.35}),
        ],
    )
    client = WorldQuantBrainSimulationClient(
        _build_settings(),
        session=session,
        sleep=lambda _: None,
        now_fn=lambda: datetime(2026, 3, 9, 8, 33, tzinfo=timezone.utc),
        monotonic_fn=lambda: 0.0,
    )

    submission = client.submit(build_sample_simulation_request())
    poll = client.poll(submission.provider_run_id)

    assert poll.status == SimulationStatus.RUNNING


def test_worldquant_brain_client_rejects_unknown_neutralization():
    session = _FakeSession(
        auth_responses=[_FakeResponse(201)],
        request_responses=[],
    )
    client = WorldQuantBrainSimulationClient(
        _build_settings(),
        session=session,
        sleep=lambda _: None,
        now_fn=lambda: datetime(2026, 3, 9, 8, 34, tzinfo=timezone.utc),
        monotonic_fn=lambda: 0.0,
    )
    request = build_sample_simulation_request().model_copy(
        update={"neutralization": "mystery_bucket"}
    )

    with pytest.raises(ValueError, match="unsupported WorldQuant Brain neutralization value"):
        client.submit(request)
