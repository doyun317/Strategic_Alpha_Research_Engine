from __future__ import annotations

from datetime import datetime, timedelta, timezone

from strategic_alpha_engine.application.contracts import (
    BrainSimulationPollResult,
    BrainSimulationResult,
    BrainSimulationSubmission,
)
from strategic_alpha_engine.domain.enums import SimulationStatus
from strategic_alpha_engine.domain.simulation import SimulationRequest

_TERMINAL_SIMULATION_STATUSES = {
    SimulationStatus.SUCCEEDED,
    SimulationStatus.FAILED,
    SimulationStatus.TIMED_OUT,
}


class FakeBrainSimulationClient:
    def __init__(
        self,
        *,
        terminal_status: SimulationStatus = SimulationStatus.SUCCEEDED,
        base_time: datetime | None = None,
        metric_seed: dict[str, float] | None = None,
    ):
        if terminal_status not in _TERMINAL_SIMULATION_STATUSES:
            raise ValueError("FakeBrainSimulationClient terminal_status must be terminal")

        resolved_base_time = base_time or datetime(2026, 1, 15, 14, 30, tzinfo=timezone.utc)
        if resolved_base_time.tzinfo is None or resolved_base_time.tzinfo.utcoffset(resolved_base_time) is None:
            raise ValueError("FakeBrainSimulationClient base_time must be timezone-aware")

        self.terminal_status = terminal_status
        self.base_time = resolved_base_time
        self.metric_seed = metric_seed or {
            "sharpe": 1.21,
            "fitness": 1.05,
            "turnover": 0.17,
            "returns": 0.14,
            "drawdown": 0.06,
        }
        self._next_run_number = 1
        self._runs: dict[str, dict[str, object]] = {}

    def submit(self, request: SimulationRequest) -> BrainSimulationSubmission:
        provider_run_id = f"brain.fake.run.{self._next_run_number:04d}"
        accepted_at = self.base_time + timedelta(minutes=self._next_run_number - 1)
        self._next_run_number += 1
        self._runs[provider_run_id] = {
            "request": request,
            "accepted_at": accepted_at,
            "poll_count": 0,
            "current_status": SimulationStatus.SUBMITTED,
        }
        return BrainSimulationSubmission(
            simulation_request_id=request.simulation_request_id,
            provider_run_id=provider_run_id,
            status=SimulationStatus.SUBMITTED,
            accepted_at=accepted_at,
            provider_message="submitted to fake brain queue",
        )

    def poll(self, provider_run_id: str) -> BrainSimulationPollResult:
        record = self._get_run_record(provider_run_id)
        statuses = [
            SimulationStatus.SUBMITTED,
            SimulationStatus.RUNNING,
            self.terminal_status,
        ]
        poll_count = int(record["poll_count"])
        status = statuses[min(poll_count, len(statuses) - 1)]
        record["current_status"] = status
        if poll_count < len(statuses) - 1:
            record["poll_count"] = poll_count + 1
        observed_at = record["accepted_at"] + timedelta(minutes=min(poll_count, len(statuses) - 1))
        return BrainSimulationPollResult(
            provider_run_id=provider_run_id,
            status=status,
            observed_at=observed_at,
            provider_message=f"fake brain status: {status.value}",
        )

    def fetch_result(self, provider_run_id: str) -> BrainSimulationResult:
        record = self._get_run_record(provider_run_id)
        current_status = record["current_status"]
        if current_status not in _TERMINAL_SIMULATION_STATUSES:
            raise ValueError("cannot fetch result before fake brain run reaches a terminal status")

        request = record["request"]
        completed_at = record["accepted_at"] + timedelta(minutes=2)
        payload = {
            "simulation_request_id": request.simulation_request_id,
            "candidate_id": request.candidate_id,
            "provider_run_id": provider_run_id,
            "status": current_status,
            "completed_at": completed_at,
            "checks": ["delay_ok", "neutralization_ok"] if current_status == SimulationStatus.SUCCEEDED else [],
            "grade": "A" if current_status == SimulationStatus.SUCCEEDED else None,
            "raw_response": {
                "provider": "fake_brain",
                "provider_run_id": provider_run_id,
                "status": current_status.value,
            },
        }
        if current_status == SimulationStatus.SUCCEEDED:
            payload.update(self.metric_seed)
        return BrainSimulationResult(**payload)

    def _get_run_record(self, provider_run_id: str) -> dict[str, object]:
        record = self._runs.get(provider_run_id)
        if record is None:
            raise ValueError(f"unknown fake brain provider_run_id: {provider_run_id}")
        return record
