from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Mapping

from pydantic import Field

from strategic_alpha_engine.domain.base import EngineModel


class EngineEnvironment(str, Enum):
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class LLMSettings(EngineModel):
    base_url: str = Field(min_length=8, max_length=500)
    model: str = Field(min_length=2, max_length=200)
    timeout_seconds: float = Field(default=30.0, gt=0.0, le=600.0)


class BrainSettings(EngineModel):
    base_url: str = Field(min_length=8, max_length=500)
    username: str | None = Field(default=None, min_length=3, max_length=320)
    password: str | None = Field(default=None, min_length=3, max_length=200)
    submit_timeout_seconds: float = Field(default=30.0, gt=0.0, le=600.0)
    poll_interval_seconds: float = Field(default=15.0, gt=0.0, le=600.0)
    max_polls: int = Field(default=120, ge=1, le=10000)


class RuntimeSettings(EngineModel):
    resolved_settings_dir: str = Field(min_length=1, max_length=500)
    loaded_env_files: list[str] = Field(default_factory=list, max_length=8)
    environment: EngineEnvironment = EngineEnvironment.DEVELOPMENT
    log_level: LogLevel = LogLevel.INFO
    region: str = Field(default="USA", min_length=2, max_length=16)
    universe: str = Field(default="TOP3000", min_length=2, max_length=32)
    default_test_period: str = Field(default="P1Y0M0D", min_length=4, max_length=32)
    simulation_delay: int = Field(default=1, ge=0, le=10)
    simulation_neutralization: str = Field(default="subindustry", min_length=2, max_length=64)
    llm: LLMSettings | None = None
    brain: BrainSettings | None = None


_DEFAULT_ENV_FILES = ("default.env", "local.env", "llm.env", "brain.env")
_LLM_KEYS = ("SAE_LLM_BASE_URL", "SAE_LLM_MODEL", "SAE_LLM_TIMEOUT_SECONDS")
_BRAIN_KEYS = (
    "SAE_BRAIN_BASE_URL",
    "SAE_BRAIN_USERNAME",
    "SAE_BRAIN_PASSWORD",
    "SAE_BRAIN_SUBMIT_TIMEOUT_SECONDS",
    "SAE_BRAIN_POLL_INTERVAL_SECONDS",
    "SAE_BRAIN_MAX_POLLS",
)


def _default_settings_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "settings"


def _strip_env_value(raw_value: str) -> str:
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _parse_env_file(path: Path) -> dict[str, str]:
    parsed: dict[str, str] = {}
    if not path.exists():
        return parsed

    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        key, separator, raw_value = line.partition("=")
        if separator != "=":
            raise ValueError(f"Malformed env line in {path.name}:{line_number}; expected KEY=VALUE")

        parsed[key.strip()] = _strip_env_value(raw_value)

    return parsed


def _resolve_env_map(
    settings_dir: Path,
    environ: Mapping[str, str],
) -> tuple[dict[str, str], list[str]]:
    merged: dict[str, str] = {}
    loaded_files: list[str] = []

    for filename in _DEFAULT_ENV_FILES:
        path = settings_dir / filename
        if not path.exists():
            continue
        merged.update(_parse_env_file(path))
        loaded_files.append(filename)

    for key, value in environ.items():
        if key.startswith("SAE_"):
            merged[key] = value

    return merged, loaded_files


def _build_llm_settings(values: Mapping[str, str]) -> LLMSettings | None:
    present_keys = [key for key in _LLM_KEYS if key in values]
    if not present_keys:
        return None

    missing = [key for key in ("SAE_LLM_BASE_URL", "SAE_LLM_MODEL") if not values.get(key)]
    if missing:
        raise ValueError(f"LLM settings are partially configured; missing: {', '.join(missing)}")

    return LLMSettings(
        base_url=values["SAE_LLM_BASE_URL"],
        model=values["SAE_LLM_MODEL"],
        timeout_seconds=values.get("SAE_LLM_TIMEOUT_SECONDS", 30.0),
    )


def _build_brain_settings(values: Mapping[str, str]) -> BrainSettings | None:
    present_keys = [key for key in _BRAIN_KEYS if key in values]
    if not present_keys:
        return None

    if not values.get("SAE_BRAIN_BASE_URL"):
        raise ValueError("Brain settings are partially configured; missing: SAE_BRAIN_BASE_URL")
    username = values.get("SAE_BRAIN_USERNAME")
    password = values.get("SAE_BRAIN_PASSWORD")
    if bool(username) != bool(password):
        raise ValueError(
            "Brain credentials are partially configured; both SAE_BRAIN_USERNAME and SAE_BRAIN_PASSWORD are required"
        )

    return BrainSettings(
        base_url=values["SAE_BRAIN_BASE_URL"],
        username=username,
        password=password,
        submit_timeout_seconds=values.get("SAE_BRAIN_SUBMIT_TIMEOUT_SECONDS", 30.0),
        poll_interval_seconds=values.get("SAE_BRAIN_POLL_INTERVAL_SECONDS", 15.0),
        max_polls=values.get("SAE_BRAIN_MAX_POLLS", 120),
    )


def load_runtime_settings(
    settings_dir: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
    require_llm: bool = False,
    require_brain: bool = False,
) -> RuntimeSettings:
    resolved_settings_dir = Path(settings_dir).expanduser().resolve() if settings_dir else _default_settings_dir()
    merged_values, loaded_files = _resolve_env_map(
        resolved_settings_dir,
        environ or os.environ,
    )

    settings = RuntimeSettings(
        resolved_settings_dir=str(resolved_settings_dir),
        loaded_env_files=loaded_files,
        environment=merged_values.get("SAE_ENV", EngineEnvironment.DEVELOPMENT),
        log_level=merged_values.get("SAE_LOG_LEVEL", LogLevel.INFO),
        region=merged_values.get("SAE_REGION", "USA"),
        universe=merged_values.get("SAE_UNIVERSE", "TOP3000"),
        default_test_period=merged_values.get("SAE_DEFAULT_TEST_PERIOD", "P1Y0M0D"),
        simulation_delay=merged_values.get("SAE_SIMULATION_DELAY", 1),
        simulation_neutralization=merged_values.get(
            "SAE_SIMULATION_NEUTRALIZATION",
            "subindustry",
        ),
        llm=_build_llm_settings(merged_values),
        brain=_build_brain_settings(merged_values),
    )

    if require_llm and settings.llm is None:
        raise ValueError("LLM settings are required but no llm.env or SAE_LLM_* overrides were found")
    if require_brain and settings.brain is None:
        raise ValueError("Brain settings are required but no brain.env or SAE_BRAIN_* overrides were found")

    return settings
