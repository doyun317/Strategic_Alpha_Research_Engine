from __future__ import annotations

import re

from pydantic import Field
from pydantic import model_validator

from strategic_alpha_engine.domain.base import EngineModel
from strategic_alpha_engine.domain.critique_report import CritiqueReport
from strategic_alpha_engine.domain.expression_candidate import ExpressionCandidate
from strategic_alpha_engine.domain.hypothesis_spec import HypothesisSpec
from strategic_alpha_engine.domain.metadata_catalog import FieldCatalogEntry
from strategic_alpha_engine.domain.research_agenda import ResearchAgenda
from strategic_alpha_engine.domain.signal_blueprint import SignalBlueprint
from strategic_alpha_engine.domain.search_policy import FamilyPolicyRecommendation

_LOOKBACK_FORBIDDEN_TRANSFORM_KINDS = {"ratio", "spread", "rank", "zscore", "log"}
_SLOT_NAME_CANDIDATES = [f"FIELD_{chr(code)}" for code in range(ord("A"), ord("Z") + 1)]


def _extract_placeholder_slots(template: str) -> list[str]:
    found = re.findall(r"\bFIELD_[A-Z0-9_]{1,31}\b", template)
    return list(dict.fromkeys(found))


def _ordered_blueprint_field_ids(blueprint: dict) -> list[str]:
    ordered: list[str] = []

    def _add(field_id: str | None) -> None:
        if isinstance(field_id, str) and field_id and field_id not in ordered:
            ordered.append(field_id)

    for field_id in blueprint.get("primary_fields", []):
        _add(field_id)
    for field_id in blueprint.get("secondary_fields", []):
        _add(field_id)
    for selection in blueprint.get("field_selections", []):
        if isinstance(selection, dict):
            _add(selection.get("field_id"))
    return ordered


def _replace_field_ids_with_slots(template: str, ordered_field_ids: list[str]) -> tuple[str, list[str]]:
    updated = template
    used_slots: list[str] = []
    for index, field_id in enumerate(ordered_field_ids):
        if index >= len(_SLOT_NAME_CANDIDATES):
            break
        pattern = rf"\b{re.escape(field_id)}\b"
        if not re.search(pattern, updated):
            continue
        slot_name = _SLOT_NAME_CANDIDATES[index]
        updated = re.sub(pattern, slot_name, updated)
        used_slots.append(slot_name)
    return updated, used_slots


def _repair_blueprint_prompt_output(payload: dict) -> dict:
    blueprint = payload.get("blueprint")
    if not isinstance(blueprint, dict):
        return payload

    for transform in blueprint.get("transform_plan", []):
        if not isinstance(transform, dict):
            continue
        kind = str(transform.get("kind", "")).lower()
        if kind in _LOOKBACK_FORBIDDEN_TRANSFORM_KINDS:
            transform.pop("lookback_days", None)

    ordered_field_ids = _ordered_blueprint_field_ids(blueprint)
    for skeleton in blueprint.get("skeleton_templates", []):
        if not isinstance(skeleton, dict):
            continue
        template = skeleton.get("template")
        if not isinstance(template, str):
            continue

        template_slots = _extract_placeholder_slots(template)
        if not template_slots:
            repaired_template, repaired_slots = _replace_field_ids_with_slots(template, ordered_field_ids)
            if repaired_slots:
                skeleton["template"] = repaired_template
                template = repaired_template
                template_slots = repaired_slots

        if template_slots:
            skeleton["slot_names"] = template_slots

    return payload


class HypothesisPlannerPromptInput(EngineModel):
    agenda: ResearchAgenda
    field_catalog_excerpt: list[FieldCatalogEntry] = Field(default_factory=list, max_length=24)
    policy_notes: list[str] = Field(default_factory=list, max_length=12)
    output_contract: str = Field(default="HypothesisSpec")


class HypothesisPlannerPromptOutput(EngineModel):
    hypothesis: HypothesisSpec
    planner_notes: list[str] = Field(default_factory=list, max_length=8)


class BlueprintBuilderPromptInput(EngineModel):
    hypothesis: HypothesisSpec
    field_catalog_excerpt: list[FieldCatalogEntry] = Field(default_factory=list, max_length=32)
    policy_notes: list[str] = Field(default_factory=list, max_length=12)
    output_contract: str = Field(default="SignalBlueprint")


class BlueprintBuilderPromptOutput(EngineModel):
    blueprint: SignalBlueprint
    design_notes: list[str] = Field(default_factory=list, max_length=12)

    @model_validator(mode="before")
    @classmethod
    def repair_llm_blueprint_payload(cls, value):
        if isinstance(value, dict):
            return _repair_blueprint_prompt_output(value)
        return value


class StrategicCriticPromptInput(EngineModel):
    hypothesis: HypothesisSpec
    blueprint: SignalBlueprint
    candidate: ExpressionCandidate
    policy_notes: list[str] = Field(default_factory=list, max_length=12)
    output_contract: str = Field(default="CritiqueReport")


class StrategicCriticPromptOutput(EngineModel):
    critique: CritiqueReport


class AgendaGeneratorPromptInput(EngineModel):
    family_recommendations: list[FamilyPolicyRecommendation] = Field(default_factory=list, max_length=24)
    recent_failed_families: list[str] = Field(default_factory=list, max_length=16)
    recent_agenda_hashes: list[str] = Field(default_factory=list, max_length=64)
    queue_depth: int = Field(default=0, ge=0, le=10000)
    target_region: str = Field(default="USA", min_length=2, max_length=16)
    target_universe: str = Field(default="TOP3000", min_length=2, max_length=32)
    enabled_families: list[str] = Field(default_factory=list, max_length=32)
    output_contract: str = Field(default="AgendaGeneratorPromptOutput")


class AgendaGeneratorPromptOutput(EngineModel):
    agendas: list[ResearchAgenda] = Field(default_factory=list, max_length=12)
    generator_notes: list[str] = Field(default_factory=list, max_length=12)
