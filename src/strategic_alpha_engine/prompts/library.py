from __future__ import annotations

import json
from enum import Enum
from pathlib import Path

from pydantic import Field

from strategic_alpha_engine.application.contracts import (
    AgendaGeneratorPromptInput,
    AgendaGeneratorPromptOutput,
    BlueprintBuilderPromptInput,
    BlueprintBuilderPromptOutput,
    HypothesisPlannerPromptInput,
    HypothesisPlannerPromptOutput,
    StrategicCriticPromptInput,
    StrategicCriticPromptOutput,
)
from strategic_alpha_engine.domain.base import EngineModel


class PromptRole(str, Enum):
    AGENDA_GENERATOR = "agenda_generator"
    PLANNER = "planner"
    BLUEPRINT = "blueprint"
    CRITIC = "critic"


class PromptAsset(EngineModel):
    prompt_id: str = Field(min_length=4, max_length=120)
    role: PromptRole
    title: str = Field(min_length=4, max_length=120)
    purpose: str = Field(min_length=12, max_length=400)
    system_instructions: str = Field(min_length=32, max_length=4000)
    input_contract: str = Field(min_length=4, max_length=120)
    output_contract: str = Field(min_length=4, max_length=120)
    temperature: float = Field(ge=0.0, le=1.0)
    notes: list[str] = Field(default_factory=list, max_length=12)
    sample_ids: list[str] = Field(default_factory=list, max_length=16)


class PromptGoldenSample(EngineModel):
    sample_id: str = Field(min_length=4, max_length=120)
    prompt_id: str = Field(min_length=4, max_length=120)
    role: PromptRole
    input_payload: dict
    output_payload: dict
    notes: list[str] = Field(default_factory=list, max_length=12)


_INPUT_CONTRACTS = {
    "AgendaGeneratorPromptInput": AgendaGeneratorPromptInput,
    "HypothesisPlannerPromptInput": HypothesisPlannerPromptInput,
    "BlueprintBuilderPromptInput": BlueprintBuilderPromptInput,
    "StrategicCriticPromptInput": StrategicCriticPromptInput,
}
_OUTPUT_CONTRACTS = {
    "AgendaGeneratorPromptOutput": AgendaGeneratorPromptOutput,
    "HypothesisPlannerPromptOutput": HypothesisPlannerPromptOutput,
    "BlueprintBuilderPromptOutput": BlueprintBuilderPromptOutput,
    "StrategicCriticPromptOutput": StrategicCriticPromptOutput,
}


def _assets_root() -> Path:
    return Path(__file__).resolve().parent / "assets"


def list_prompt_assets() -> list[PromptAsset]:
    assets: list[PromptAsset] = []
    for path in sorted((_assets_root() / "roles").rglob("*.json")):
        assets.append(PromptAsset(**json.loads(path.read_text(encoding="utf-8"))))
    return assets


def load_prompt_asset(role: PromptRole | str) -> PromptAsset:
    normalized_role = PromptRole(role)
    path = _assets_root() / "roles" / f"{normalized_role.value}.json"
    return PromptAsset(**json.loads(path.read_text(encoding="utf-8")))


def list_prompt_golden_samples(role: PromptRole | str | None = None) -> list[PromptGoldenSample]:
    samples: list[PromptGoldenSample] = []
    root = _assets_root() / "golden"
    if role is None:
        paths = sorted(root.rglob("*.json"))
    else:
        normalized_role = PromptRole(role)
        paths = sorted((root / normalized_role.value).rglob("*.json"))

    for path in paths:
        samples.append(PromptGoldenSample(**json.loads(path.read_text(encoding="utf-8"))))
    return samples


def load_prompt_golden_sample(role: PromptRole | str, sample_id: str) -> PromptGoldenSample:
    for sample in list_prompt_golden_samples(role):
        if sample.sample_id == sample_id:
            return sample
    raise ValueError(f"Unknown prompt golden sample: role={role}, sample_id={sample_id}")


def validate_prompt_golden_sample(sample: PromptGoldenSample) -> None:
    asset = load_prompt_asset(sample.role)
    input_contract = _INPUT_CONTRACTS[asset.input_contract]
    output_contract = _OUTPUT_CONTRACTS[asset.output_contract]
    input_contract(**sample.input_payload)
    output_contract(**sample.output_payload)
