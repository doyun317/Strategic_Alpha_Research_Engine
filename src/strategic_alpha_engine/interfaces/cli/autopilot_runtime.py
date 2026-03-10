from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from strategic_alpha_engine.application.services import (
    FamilyWeightedAgendaPrioritizer,
    HeuristicResearchAgendaManager,
    HybridAgendaGenerator,
    LLMAgendaAugmentor,
    LLMBlueprintBuilder,
    LLMHypothesisPlanner,
    LLMStrategicCritic,
    LocalArtifactFamilyAnalyticsBuilder,
    MetadataBackedStaticValidator,
    RuleBasedRobustPromotionDecider,
    RuleBasedStageAEvaluator,
    RuleBasedStageAPromotionDecider,
    RuleBasedValidationRunner,
    SkeletonCandidateSynthesizer,
    StructuredLLMClient,
    TemplateAgendaGenerator,
)
from strategic_alpha_engine.application.workflows import (
    AutopilotWorkflow,
    HumanReviewWorkflow,
    MultiPeriodValidateWorkflow,
    PlanWorkflow,
    RobustPromotionWorkflow,
    StageAEvaluationWorkflow,
    SubmissionPacketWorkflow,
    SynthesizeWorkflow,
    ValidateWorkflow,
)
from strategic_alpha_engine.config import RuntimeSettings
from strategic_alpha_engine.domain import ResearchAgenda
from strategic_alpha_engine.domain.enums import SimulationStatus
from strategic_alpha_engine.infrastructure.artifacts import LocalFileArtifactLedger
from strategic_alpha_engine.infrastructure.brain import (
    FakeBrainSimulationClient,
    WorldQuantBrainSimulationClient,
)
from strategic_alpha_engine.infrastructure.llm import OpenAICompatibleStructuredLLMClient
from strategic_alpha_engine.infrastructure.metadata import load_seed_metadata_catalog
from strategic_alpha_engine.infrastructure.state import LocalFileStateLedger


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _read_jsonl_file(path: Path) -> list[dict]:
    if not path.exists():
        return []
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        return []
    return [json.loads(line) for line in content.splitlines()]


def build_structured_llm_client(settings: RuntimeSettings) -> StructuredLLMClient:
    if settings.llm is None:
        raise ValueError("LLM settings are required for autopilot execution")
    return OpenAICompatibleStructuredLLMClient(settings.llm)


def build_autopilot_plan_workflow(settings: RuntimeSettings) -> PlanWorkflow:
    llm_client = build_structured_llm_client(settings)
    return PlanWorkflow(
        hypothesis_planner=LLMHypothesisPlanner(llm_client),
        blueprint_builder=LLMBlueprintBuilder(llm_client),
    )


def build_autopilot_synthesize_workflow(settings: RuntimeSettings) -> SynthesizeWorkflow:
    llm_client = build_structured_llm_client(settings)
    return SynthesizeWorkflow(
        candidate_synthesizer=SkeletonCandidateSynthesizer(),
        static_validator=MetadataBackedStaticValidator(load_seed_metadata_catalog()),
        strategic_critic=LLMStrategicCritic(llm_client),
    )


def load_agenda_catalog(path: str | None) -> list[ResearchAgenda]:
    if not path:
        return []

    catalog_path = Path(path)
    if catalog_path.suffix == ".jsonl":
        return [ResearchAgenda(**payload) for payload in _read_jsonl_file(catalog_path)]

    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [ResearchAgenda(**item) for item in payload]
    if isinstance(payload, dict) and "agendas" in payload and isinstance(payload["agendas"], list):
        return [ResearchAgenda(**item) for item in payload["agendas"]]
    if isinstance(payload, dict):
        return [ResearchAgenda(**payload)]
    raise ValueError("agenda catalog input must be a JSON object, JSON array, or JSONL file")


def _build_brain_client(
    *,
    settings: RuntimeSettings,
    brain_provider: str,
    fake_terminal_status: str,
    started_at: datetime,
):
    if brain_provider == "fake":
        return FakeBrainSimulationClient(
            terminal_status=SimulationStatus(fake_terminal_status),
            base_time=started_at - timedelta(minutes=5),
        )

    if settings.brain is None:
        raise ValueError("Brain settings are required when --brain-provider=worldquant")

    return WorldQuantBrainSimulationClient(settings.brain)


def _build_stage_a_workflow() -> StageAEvaluationWorkflow:
    return StageAEvaluationWorkflow(
        evaluator=RuleBasedStageAEvaluator(),
        promotion_decider=RuleBasedStageAPromotionDecider(),
    )


def _build_multi_period_validate_workflow(
    *,
    base_time: datetime | None = None,
    minimum_passing_periods: int = 2,
) -> MultiPeriodValidateWorkflow:
    return MultiPeriodValidateWorkflow(
        validate_workflow=ValidateWorkflow(
            validation_runner=RuleBasedValidationRunner(base_time=base_time),
        ),
        minimum_passing_periods=minimum_passing_periods,
    )


def _build_robust_promotion_workflow() -> RobustPromotionWorkflow:
    return RobustPromotionWorkflow(
        promotion_decider=RuleBasedRobustPromotionDecider(),
    )


def _build_human_review_workflow() -> HumanReviewWorkflow:
    return HumanReviewWorkflow()


def _build_submission_packet_workflow() -> SubmissionPacketWorkflow:
    return SubmissionPacketWorkflow()


def build_autopilot_workflow(
    *,
    settings: RuntimeSettings,
    artifacts_dir: str,
    brain_provider: str,
    fake_terminal_status: str,
    max_polls: int | None,
) -> AutopilotWorkflow:
    llm_client = build_structured_llm_client(settings)
    return AutopilotWorkflow(
        settings=settings,
        agenda_generator=HybridAgendaGenerator(
            TemplateAgendaGenerator(
                regions=[settings.region],
                universes=[settings.universe],
            ),
            LLMAgendaAugmentor(
                llm_client,
                target_region=settings.region,
                target_universe=settings.universe,
            ),
            min_queue_depth=settings.autopilot.min_queue_depth,
        ),
        agenda_manager=HeuristicResearchAgendaManager(
            agenda_prioritizer=FamilyWeightedAgendaPrioritizer(),
        ),
        plan_workflow=build_autopilot_plan_workflow(settings),
        synthesize_workflow=build_autopilot_synthesize_workflow(settings),
        brain_client=_build_brain_client(
            settings=settings,
            brain_provider=brain_provider,
            fake_terminal_status=fake_terminal_status,
            started_at=_utc_now(),
        ),
        stage_a_workflow=_build_stage_a_workflow(),
        validate_workflow=_build_multi_period_validate_workflow(base_time=_utc_now()),
        robust_promotion_workflow=_build_robust_promotion_workflow(),
        human_review_workflow=_build_human_review_workflow(),
        submission_packet_workflow=_build_submission_packet_workflow(),
        artifact_ledger=LocalFileArtifactLedger(artifacts_dir),
        state_ledger=LocalFileStateLedger(artifacts_dir),
        family_analytics_builder=LocalArtifactFamilyAnalyticsBuilder(),
        max_polls=max_polls or (settings.brain.max_polls if settings.brain else 3),
    )
