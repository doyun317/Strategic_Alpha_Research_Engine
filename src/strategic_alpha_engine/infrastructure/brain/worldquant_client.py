from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from time import monotonic, sleep as default_sleep
from typing import Any, Callable
from urllib.parse import urljoin

import requests

from strategic_alpha_engine.application.contracts import (
    BrainSimulationPollResult,
    BrainSimulationResult,
    BrainSimulationSubmission,
)
from strategic_alpha_engine.config import BrainSettings
from strategic_alpha_engine.domain.enums import SimulationStatus
from strategic_alpha_engine.domain.simulation import SimulationRequest

_ACTIVE_PROGRESS_STATUSES = {
    "PENDING": SimulationStatus.SUBMITTED,
    "RUNNING": SimulationStatus.RUNNING,
}
_TERMINAL_PROGRESS_STATUSES = {
    "COMPLETE": SimulationStatus.SUCCEEDED,
    "FAILED": SimulationStatus.FAILED,
    "ERROR": SimulationStatus.FAILED,
}
_DEFAULT_WORLDQUANT_SIMULATION_SETTINGS = {
    "instrumentType": "EQUITY",
    "decay": 0,
    "truncation": 0.08,
    "pasteurization": "ON",
    "unitHandling": "VERIFY",
    "nanHandling": "OFF",
    "language": "FASTEXPR",
    "visualization": False,
}


@dataclass
class _SubmittedRequestState:
    request: SimulationRequest
    progress_url: str
    accepted_at: datetime
    latest_progress_payload: dict[str, Any]
    latest_status: SimulationStatus
    alpha_id: str | None = None
    next_poll_not_before: float = 0.0


class WorldQuantBrainSimulationClient:
    def __init__(
        self,
        settings: BrainSettings,
        *,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = default_sleep,
        now_fn: Callable[[], datetime] | None = None,
        monotonic_fn: Callable[[], float] = monotonic,
    ):
        if not settings.username or not settings.password:
            raise ValueError(
                "WorldQuantBrainSimulationClient requires SAE_BRAIN_USERNAME and SAE_BRAIN_PASSWORD"
            )

        self.settings = settings
        self._session = session or requests.Session()
        self._sleep = sleep
        self._now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self._monotonic_fn = monotonic_fn
        self._states: dict[str, _SubmittedRequestState] = {}
        self._authenticate()

    def submit(self, request: SimulationRequest) -> BrainSimulationSubmission:
        response = self._request(
            "POST",
            "/simulations",
            json=self._build_submit_payload(request),
            timeout=self.settings.submit_timeout_seconds,
        )
        if response.status_code != 201:
            raise RuntimeError(
                f"WorldQuant Brain simulation submit failed with status {response.status_code}: {response.text[:240]}"
            )

        progress_url = self._resolve_progress_url(response.headers.get("Location"))
        accepted_at = self._now_fn()
        state = _SubmittedRequestState(
            request=request,
            progress_url=progress_url,
            accepted_at=accepted_at,
            latest_progress_payload={"status": "PENDING", "progress_url": progress_url},
            latest_status=SimulationStatus.SUBMITTED,
            next_poll_not_before=self._monotonic_fn(),
        )
        self._states[progress_url] = state
        return BrainSimulationSubmission(
            simulation_request_id=request.simulation_request_id,
            provider_run_id=progress_url,
            status=SimulationStatus.SUBMITTED,
            accepted_at=accepted_at,
            provider_message="submitted to WorldQuant Brain",
        )

    def poll(self, provider_run_id: str) -> BrainSimulationPollResult:
        state = self._get_state(provider_run_id)
        self._wait_until_next_poll(state)
        response = self._poll_progress_url(state.progress_url)
        payload = self._decode_json(response)
        status = self._map_progress_status(payload)
        retry_after = self._parse_retry_after(response.headers.get("Retry-After"))
        state.latest_progress_payload = payload
        state.latest_status = status
        state.alpha_id = payload.get("alpha") or state.alpha_id
        state.next_poll_not_before = self._monotonic_fn() + (
            retry_after or self.settings.poll_interval_seconds
        )
        return BrainSimulationPollResult(
            provider_run_id=provider_run_id,
            status=status,
            observed_at=self._now_fn(),
            provider_message=payload.get("message") or payload.get("status"),
        )

    def fetch_result(self, provider_run_id: str) -> BrainSimulationResult:
        state = self._get_state(provider_run_id)
        if state.latest_status not in {
            SimulationStatus.SUCCEEDED,
            SimulationStatus.FAILED,
            SimulationStatus.TIMED_OUT,
        }:
            raise ValueError("cannot fetch result before WorldQuant Brain run reaches a terminal status")

        if state.latest_status != SimulationStatus.SUCCEEDED:
            return BrainSimulationResult(
                simulation_request_id=state.request.simulation_request_id,
                candidate_id=state.request.candidate_id,
                provider_run_id=provider_run_id,
                status=state.latest_status,
                completed_at=self._now_fn(),
                raw_response={"progress": state.latest_progress_payload},
            )

        alpha_id = state.alpha_id or state.latest_progress_payload.get("alpha")
        if not alpha_id:
            raise RuntimeError("WorldQuant Brain progress payload did not include an alpha id")

        response = self._request(
            "GET",
            f"/alphas/{alpha_id}",
            timeout=self.settings.submit_timeout_seconds,
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"WorldQuant Brain alpha fetch failed with status {response.status_code}: {response.text[:240]}"
            )

        alpha_payload = self._decode_json(response)
        metrics = self._build_metrics(alpha_payload)
        return BrainSimulationResult(
            simulation_request_id=state.request.simulation_request_id,
            candidate_id=state.request.candidate_id,
            provider_run_id=provider_run_id,
            status=SimulationStatus.SUCCEEDED,
            completed_at=self._now_fn(),
            sharpe=metrics["sharpe"],
            fitness=metrics["fitness"],
            turnover=metrics["turnover"],
            returns=metrics["returns"],
            drawdown=metrics["drawdown"],
            checks=metrics["checks"],
            grade=metrics["grade"],
            raw_response={
                "progress": state.latest_progress_payload,
                "alpha": alpha_payload,
            },
        )

    def _authenticate(self) -> None:
        self._session.auth = (self.settings.username, self.settings.password)
        self._session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )
        response = self._session.post(
            self._build_url("/authentication"),
            timeout=self.settings.submit_timeout_seconds,
        )
        if response.status_code != 201:
            raise RuntimeError(
                f"WorldQuant Brain authentication failed with status {response.status_code}: {response.text[:240]}"
            )

    def _request(
        self,
        method: str,
        path_or_url: str,
        *,
        json: dict[str, Any] | None = None,
        timeout: float | None = None,
        allow_reauth: bool = True,
    ) -> requests.Response:
        response = self._session.request(
            method,
            self._build_url(path_or_url),
            json=json,
            timeout=timeout or self.settings.submit_timeout_seconds,
        )
        if response.status_code == 401 and allow_reauth:
            self._authenticate()
            return self._request(
                method,
                path_or_url,
                json=json,
                timeout=timeout,
                allow_reauth=False,
            )
        return response

    def _poll_progress_url(self, progress_url: str) -> requests.Response:
        while True:
            response = self._request(
                "GET",
                progress_url,
                timeout=self.settings.submit_timeout_seconds,
            )
            if response.status_code == 429:
                self._sleep(
                    self._parse_retry_after(response.headers.get("Retry-After"))
                    or self.settings.poll_interval_seconds
                )
                continue
            if response.status_code != 200:
                raise RuntimeError(
                    f"WorldQuant Brain progress poll failed with status {response.status_code}: {response.text[:240]}"
                )
            return response

    def _wait_until_next_poll(self, state: _SubmittedRequestState) -> None:
        remaining = state.next_poll_not_before - self._monotonic_fn()
        if remaining > 0:
            self._sleep(remaining)

    def _build_submit_payload(self, request: SimulationRequest) -> dict[str, Any]:
        return {
            "type": "REGULAR",
            "settings": {
                **_DEFAULT_WORLDQUANT_SIMULATION_SETTINGS,
                "region": request.region,
                "universe": request.universe,
                "delay": request.delay,
                "neutralization": request.neutralization,
            },
            "regular": request.expression,
        }

    def _build_metrics(self, alpha_payload: dict[str, Any]) -> dict[str, Any]:
        is_payload = alpha_payload.get("is") or {}
        sharpe = self._coerce_float(is_payload.get("sharpe"))
        fitness = self._coerce_float(is_payload.get("fitness"))
        turnover = self._coerce_float(is_payload.get("turnover"))
        checks = [
            check.get("name")
            for check in is_payload.get("checks", [])
            if isinstance(check, dict) and check.get("name")
        ]
        returns = self._coerce_float(is_payload.get("returns"))
        if returns is None:
            returns = self._coerce_float(is_payload.get("margin"))
            if returns is not None and "returns_fallback_margin" not in checks:
                checks.append("returns_fallback_margin")
        drawdown = self._coerce_float(is_payload.get("drawdown"))
        if drawdown is None:
            drawdown = 0.0
            if "drawdown_missing_defaulted" not in checks:
                checks.append("drawdown_missing_defaulted")

        if sharpe is None or fitness is None or turnover is None or returns is None:
            raise RuntimeError("WorldQuant Brain alpha payload did not include required performance metrics")

        return {
            "sharpe": sharpe,
            "fitness": fitness,
            "turnover": turnover,
            "returns": returns,
            "drawdown": drawdown,
            "checks": checks,
            "grade": self._derive_grade(sharpe, fitness),
        }

    def _map_progress_status(self, payload: dict[str, Any]) -> SimulationStatus:
        raw_status = str(payload.get("status", "")).upper()
        if raw_status in _ACTIVE_PROGRESS_STATUSES:
            return _ACTIVE_PROGRESS_STATUSES[raw_status]
        if raw_status in _TERMINAL_PROGRESS_STATUSES:
            return _TERMINAL_PROGRESS_STATUSES[raw_status]
        raise RuntimeError(f"unsupported WorldQuant Brain progress status: {raw_status or 'missing'}")

    def _resolve_progress_url(self, location: str | None) -> str:
        if not location:
            raise RuntimeError("WorldQuant Brain submit response did not include a Location header")
        return self._build_url(location)

    def _build_url(self, path_or_url: str) -> str:
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            return path_or_url
        return urljoin(self.settings.base_url.rstrip("/") + "/", path_or_url.lstrip("/"))

    def _get_state(self, provider_run_id: str) -> _SubmittedRequestState:
        state = self._states.get(provider_run_id)
        if state is None:
            raise ValueError(f"unknown WorldQuant Brain provider_run_id: {provider_run_id}")
        return state

    def _decode_json(self, response: requests.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError("WorldQuant Brain response was not valid JSON") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("WorldQuant Brain response JSON must be an object")
        return payload

    def _parse_retry_after(self, raw_value: str | None) -> float | None:
        if raw_value in (None, ""):
            return None
        try:
            return max(float(raw_value), 0.0)
        except ValueError:
            return self.settings.poll_interval_seconds

    def _coerce_float(self, value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _derive_grade(self, sharpe: float, fitness: float) -> str:
        if sharpe >= 1.5 and fitness >= 1.0:
            return "A"
        if sharpe >= 1.0 and fitness >= 0.7:
            return "B"
        if sharpe >= 0.5 and fitness >= 0.3:
            return "C"
        return "D"
