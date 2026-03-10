from __future__ import annotations

from collections.abc import Iterable
from hashlib import sha1

from strategic_alpha_engine.application.contracts import (
    AgendaGeneratorPromptInput,
    AgendaGeneratorPromptOutput,
    FamilyLearnerSummary,
)
from strategic_alpha_engine.application.services.search_policy import HeuristicSearchPolicyLearner
from strategic_alpha_engine.application.services.interfaces import AgendaGenerator, StructuredLLMClient
from strategic_alpha_engine.domain.enums import ResearchFamily, ResearchHorizon
from strategic_alpha_engine.domain.research_agenda import ResearchAgenda
from strategic_alpha_engine.prompts import PromptRole, load_prompt_asset


_DEFAULT_HORIZON_BY_FAMILY = {
    ResearchFamily.MEAN_REVERSION: ResearchHorizon.SHORT,
    ResearchFamily.MOMENTUM: ResearchHorizon.MEDIUM,
    ResearchFamily.QUALITY_VALUE: ResearchHorizon.LONG,
    ResearchFamily.QUALITY_DETERIORATION: ResearchHorizon.MEDIUM,
    ResearchFamily.LIQUIDITY_STRESS: ResearchHorizon.SHORT,
    ResearchFamily.REVISION_DRIFT: ResearchHorizon.MEDIUM,
    ResearchFamily.VOLATILITY_REGIME: ResearchHorizon.SHORT,
    ResearchFamily.FLOW_LIQUIDITY: ResearchHorizon.MEDIUM,
}

_MOTIVATION_TEMPLATES = {
    ResearchFamily.MEAN_REVERSION: "Probe short-horizon overreaction reversion with bounded transforms and strict normalization.",
    ResearchFamily.MOMENTUM: "Probe continuation effects with conservative volatility-aware normalization and bounded operators.",
    ResearchFamily.QUALITY_VALUE: "Probe slow-moving quality and value spreads while preserving conservative denominator guards.",
    ResearchFamily.QUALITY_DETERIORATION: "Probe worsening balance-sheet or cash-generation quality under conservative normalization.",
    ResearchFamily.LIQUIDITY_STRESS: "Probe liquidity shocks and turnover stress while avoiding fragile trade gating constructs.",
    ResearchFamily.REVISION_DRIFT: "Probe estimate-revision drift under medium-horizon expression constraints and stable operators.",
    ResearchFamily.VOLATILITY_REGIME: "Probe regime-sensitive volatility dislocations with explicit ranking and bounded lookbacks.",
    ResearchFamily.FLOW_LIQUIDITY: "Probe flow and liquidity imbalance effects while preserving tradability-aware controls.",
}


def _enum_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def agenda_dedupe_key(agenda: ResearchAgenda) -> tuple[str, str, str, tuple[str, ...], str]:
    normalized_motivation = " ".join(agenda.motivation.lower().split())
    return (
        _enum_value(agenda.family),
        agenda.target_region,
        agenda.target_universe,
        tuple(sorted(_enum_value(horizon) for horizon in agenda.target_horizons)),
        sha1(normalized_motivation.encode("utf-8")).hexdigest()[:16],
    )


def dedupe_agendas(agendas: Iterable[ResearchAgenda]) -> list[ResearchAgenda]:
    deduped: list[ResearchAgenda] = []
    seen: set[tuple[str, str, str, tuple[str, ...], str]] = set()
    for agenda in agendas:
        if agenda.status not in {"active", "backlog"}:
            continue
        key = agenda_dedupe_key(agenda)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(agenda)
    return deduped


class TemplateAgendaGenerator(AgendaGenerator):
    def __init__(
        self,
        *,
        enabled_families: list[ResearchFamily] | None = None,
        regions: list[str] | None = None,
        universes: list[str] | None = None,
        horizons: list[ResearchHorizon] | None = None,
        owner: str = "autopilot",
    ):
        self.enabled_families = enabled_families or list(ResearchFamily)
        self.regions = regions or ["USA"]
        self.universes = universes or ["TOP3000"]
        self.horizons = horizons or list(ResearchHorizon)
        self.owner = owner

    def generate(
        self,
        *,
        existing_agendas: list[ResearchAgenda],
        queue_depth: int,
        learner_summaries: list[FamilyLearnerSummary],
        recent_failed_families: list[ResearchFamily],
    ) -> list[ResearchAgenda]:
        del queue_depth, learner_summaries, recent_failed_families

        existing_keys = {agenda_dedupe_key(agenda) for agenda in existing_agendas}
        generated: list[ResearchAgenda] = []
        for family in self.enabled_families:
            default_horizon = _DEFAULT_HORIZON_BY_FAMILY[family]
            for region in self.regions:
                for universe in self.universes:
                    horizon_candidates = [
                        horizon
                        for horizon in self.horizons
                        if horizon == default_horizon
                    ] or [default_horizon]
                    for horizon in horizon_candidates:
                        agenda = ResearchAgenda(
                            agenda_id=(
                                f"agenda.autopilot.{_enum_value(family)}.{region.lower()}."
                                f"{universe.lower()}.{_enum_value(horizon)}"
                            ),
                            name=f"{_enum_value(family).replace('_', ' ').title()} {_enum_value(horizon)} autopilot sweep",
                            family=family,
                            priority=0.6,
                            target_region=region,
                            target_universe=universe,
                            target_horizons=[horizon],
                            motivation=_MOTIVATION_TEMPLATES[family],
                            constraints=["require_cross_sectional_normalization", "avoid_fragile_control_flow"],
                            tags=[_enum_value(family), _enum_value(horizon), "autopilot"],
                            owner=self.owner,
                            status="backlog",
                        )
                        key = agenda_dedupe_key(agenda)
                        if key in existing_keys:
                            continue
                        existing_keys.add(key)
                        generated.append(agenda)
        return generated


class LLMAgendaAugmentor(AgendaGenerator):
    def __init__(
        self,
        structured_llm_client: StructuredLLMClient,
        *,
        target_region: str,
        target_universe: str,
        enabled_families: list[ResearchFamily] | None = None,
    ):
        self.structured_llm_client = structured_llm_client
        self.target_region = target_region
        self.target_universe = target_universe
        self.enabled_families = enabled_families or list(ResearchFamily)
        self.asset = load_prompt_asset(PromptRole.AGENDA_GENERATOR)
        self.policy_learner = HeuristicSearchPolicyLearner()

    def generate(
        self,
        *,
        existing_agendas: list[ResearchAgenda],
        queue_depth: int,
        learner_summaries: list[FamilyLearnerSummary],
        recent_failed_families: list[ResearchFamily],
    ) -> list[ResearchAgenda]:
        recommendations = self.policy_learner.recommend(learner_summaries)
        prompt_input = AgendaGeneratorPromptInput(
            family_recommendations=recommendations,
            recent_failed_families=[_enum_value(family) for family in recent_failed_families],
            recent_agenda_hashes=[
                agenda_dedupe_key(agenda)[-1]
                for agenda in existing_agendas[-32:]
            ],
            queue_depth=queue_depth,
            target_region=self.target_region,
            target_universe=self.target_universe,
            enabled_families=[_enum_value(family) for family in self.enabled_families],
        )
        response = self.structured_llm_client.generate_structured(
            asset=self.asset,
            input_payload=prompt_input.model_dump(mode="json"),
            output_model=AgendaGeneratorPromptOutput,
        )
        normalized: list[ResearchAgenda] = []
        for index, agenda in enumerate(response.agendas, start=1):
            payload = agenda.model_dump(mode="json")
            payload.setdefault("agenda_id", f"agenda.autollm.{index:03d}")
            payload.setdefault("owner", "autopilot_llm")
            if payload.get("status") not in {"active", "backlog"}:
                payload["status"] = "backlog"
            normalized.append(ResearchAgenda(**payload))
        return dedupe_agendas([*existing_agendas, *normalized])[len(dedupe_agendas(existing_agendas)) :]


class HybridAgendaGenerator(AgendaGenerator):
    def __init__(
        self,
        template_generator: TemplateAgendaGenerator,
        llm_augmentor: LLMAgendaAugmentor,
        *,
        min_queue_depth: int = 5,
    ):
        self.template_generator = template_generator
        self.llm_augmentor = llm_augmentor
        self.min_queue_depth = min_queue_depth
        self.last_summary = {
            "template_generated_count": 0,
            "llm_generated_count": 0,
            "returned_count": 0,
            "queue_depth": 0,
        }

    def generate(
        self,
        *,
        existing_agendas: list[ResearchAgenda],
        queue_depth: int,
        learner_summaries: list[FamilyLearnerSummary],
        recent_failed_families: list[ResearchFamily],
    ) -> list[ResearchAgenda]:
        template_agendas = self.template_generator.generate(
            existing_agendas=existing_agendas,
            queue_depth=queue_depth,
            learner_summaries=learner_summaries,
            recent_failed_families=recent_failed_families,
        )
        llm_agendas: list[ResearchAgenda] = []
        if queue_depth <= self.min_queue_depth:
            llm_agendas = self.llm_augmentor.generate(
                existing_agendas=[*existing_agendas, *template_agendas],
                queue_depth=queue_depth,
                learner_summaries=learner_summaries,
                recent_failed_families=recent_failed_families,
            )

        combined = dedupe_agendas([*template_agendas, *llm_agendas])
        self.last_summary = {
            "template_generated_count": len(template_agendas),
            "llm_generated_count": len(llm_agendas),
            "returned_count": len(combined),
            "queue_depth": queue_depth,
        }
        return combined
