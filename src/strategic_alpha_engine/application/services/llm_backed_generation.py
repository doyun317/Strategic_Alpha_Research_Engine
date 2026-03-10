from __future__ import annotations

from strategic_alpha_engine.application.contracts import (
    BlueprintBuilderPromptInput,
    BlueprintBuilderPromptOutput,
    HypothesisPlannerPromptInput,
    HypothesisPlannerPromptOutput,
    StrategicCriticPromptInput,
    StrategicCriticPromptOutput,
)
from strategic_alpha_engine.application.services.interfaces import StructuredLLMClient
from strategic_alpha_engine.domain.critique_report import CritiqueReport
from strategic_alpha_engine.domain.hypothesis_spec import HypothesisSpec
from strategic_alpha_engine.domain.metadata_catalog import MetadataCatalog
from strategic_alpha_engine.domain.research_agenda import ResearchAgenda
from strategic_alpha_engine.domain.signal_blueprint import SignalBlueprint
from strategic_alpha_engine.infrastructure.metadata import load_seed_metadata_catalog
from strategic_alpha_engine.prompts import PromptRole, load_prompt_asset


class LLMHypothesisPlanner:
    def __init__(
        self,
        structured_llm_client: StructuredLLMClient,
        *,
        metadata_catalog: MetadataCatalog | None = None,
    ):
        self.structured_llm_client = structured_llm_client
        self.metadata_catalog = metadata_catalog or load_seed_metadata_catalog()
        self.asset = load_prompt_asset(PromptRole.PLANNER)

    def plan(self, agenda: ResearchAgenda) -> HypothesisSpec:
        prompt_input = HypothesisPlannerPromptInput(
            agenda=agenda,
            field_catalog_excerpt=self.metadata_catalog.build_field_excerpt(
                horizons=agenda.target_horizons,
                limit=12,
            ),
            policy_notes=[
                "Preserve agenda family and horizon exactly.",
                "Prefer conservative field classes and explicit normalization language.",
            ],
        )
        response = self.structured_llm_client.generate_structured(
            asset=self.asset,
            input_payload=prompt_input.model_dump(mode="json"),
            output_model=HypothesisPlannerPromptOutput,
        )
        hypothesis_payload = response.hypothesis.model_dump(mode="json")
        hypothesis_payload.update(
            {
                "agenda_id": agenda.agenda_id,
                "family": agenda.family,
                "horizon": agenda.target_horizons[0],
                "target_region": agenda.target_region,
                "target_universe": agenda.target_universe,
            }
        )
        return HypothesisSpec(**hypothesis_payload)


class LLMBlueprintBuilder:
    def __init__(
        self,
        structured_llm_client: StructuredLLMClient,
        *,
        metadata_catalog: MetadataCatalog | None = None,
    ):
        self.structured_llm_client = structured_llm_client
        self.metadata_catalog = metadata_catalog or load_seed_metadata_catalog()
        self.asset = load_prompt_asset(PromptRole.BLUEPRINT)

    def build(self, hypothesis: HypothesisSpec) -> SignalBlueprint:
        prompt_input = BlueprintBuilderPromptInput(
            hypothesis=hypothesis,
            field_catalog_excerpt=self.metadata_catalog.build_field_excerpt(
                field_classes=hypothesis.field_classes,
                horizons=[hypothesis.horizon],
                limit=16,
            ),
            policy_notes=[
                "All primary_fields must be present in field_selections.",
                "Final normalization must satisfy operator_policy.require_outer_normalization.",
            ],
        )
        response = self.structured_llm_client.generate_structured(
            asset=self.asset,
            input_payload=prompt_input.model_dump(mode="json"),
            output_model=BlueprintBuilderPromptOutput,
        )
        blueprint_payload = response.blueprint.model_dump(mode="json")
        blueprint_payload["hypothesis_id"] = hypothesis.hypothesis_id
        return SignalBlueprint(**blueprint_payload)


class LLMStrategicCritic:
    def __init__(self, structured_llm_client: StructuredLLMClient):
        self.structured_llm_client = structured_llm_client
        self.asset = load_prompt_asset(PromptRole.CRITIC)

    def critique(
        self,
        hypothesis: HypothesisSpec,
        blueprint: SignalBlueprint,
        candidate,
    ) -> CritiqueReport:
        prompt_input = StrategicCriticPromptInput(
            hypothesis=hypothesis,
            blueprint=blueprint,
            candidate=candidate,
            policy_notes=[
                "Reject any candidate with high-severity structural or horizon-alignment issues.",
                "Prefer conservative feedback over permissive passing.",
            ],
        )
        response = self.structured_llm_client.generate_structured(
            asset=self.asset,
            input_payload=prompt_input.model_dump(mode="json"),
            output_model=StrategicCriticPromptOutput,
        )
        critique_payload = response.critique.model_dump(mode="json")
        critique_payload["candidate_id"] = candidate.candidate_id
        critique_payload["blueprint_id"] = blueprint.blueprint_id
        critique_payload.setdefault("critic_name", "llm_strategic_critic")
        return CritiqueReport(**critique_payload)

