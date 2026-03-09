from __future__ import annotations

from pydantic import Field

from strategic_alpha_engine.domain.base import EngineModel
from strategic_alpha_engine.domain.critique_report import CritiqueReport
from strategic_alpha_engine.domain.enums import FieldClass, UpdateCadence
from strategic_alpha_engine.domain.expression_candidate import ExpressionCandidate
from strategic_alpha_engine.domain.hypothesis_spec import HypothesisSpec
from strategic_alpha_engine.domain.research_agenda import ResearchAgenda
from strategic_alpha_engine.domain.signal_blueprint import SignalBlueprint


class FieldCatalogEntry(EngineModel):
    field_id: str = Field(min_length=2, max_length=64)
    field_class: FieldClass
    update_cadence: UpdateCadence
    description: str = Field(min_length=8, max_length=240)
    recommended_horizons: list[str] = Field(default_factory=list, max_length=4)
    discouraged_patterns: list[str] = Field(default_factory=list, max_length=8)


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


class StrategicCriticPromptInput(EngineModel):
    hypothesis: HypothesisSpec
    blueprint: SignalBlueprint
    candidate: ExpressionCandidate
    policy_notes: list[str] = Field(default_factory=list, max_length=12)
    output_contract: str = Field(default="CritiqueReport")


class StrategicCriticPromptOutput(EngineModel):
    critique: CritiqueReport

