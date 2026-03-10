from __future__ import annotations

from pydantic import Field

from strategic_alpha_engine.domain.base import EngineModel
from strategic_alpha_engine.domain.critique_report import CritiqueReport
from strategic_alpha_engine.domain.expression_candidate import ExpressionCandidate
from strategic_alpha_engine.domain.hypothesis_spec import HypothesisSpec
from strategic_alpha_engine.domain.metadata_catalog import FieldCatalogEntry
from strategic_alpha_engine.domain.research_agenda import ResearchAgenda
from strategic_alpha_engine.domain.signal_blueprint import SignalBlueprint
from strategic_alpha_engine.domain.search_policy import FamilyPolicyRecommendation


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
