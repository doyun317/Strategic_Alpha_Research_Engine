from datetime import datetime, timezone

from strategic_alpha_engine.application.contracts import (
    AgendaGeneratorPromptOutput,
    FamilyLearnerSummary,
)
from strategic_alpha_engine.application.services.agenda_generation import (
    HybridAgendaGenerator,
    LLMAgendaAugmentor,
    TemplateAgendaGenerator,
    agenda_dedupe_key,
)
from strategic_alpha_engine.domain.enums import ResearchFamily
from strategic_alpha_engine.domain.research_agenda import ResearchAgenda


class _StubStructuredLLMClient:
    def __init__(self, agendas: list[ResearchAgenda]):
        self.agendas = agendas
        self.calls = 0

    def generate_structured(self, *, asset, input_payload, output_model):
        del asset, input_payload
        self.calls += 1
        return output_model(
            agendas=self.agendas,
            generator_notes=["stubbed"],
        )


def test_template_agenda_generator_is_deterministic_and_dedupes_existing():
    generator = TemplateAgendaGenerator()
    existing = [
        ResearchAgenda(
            agenda_id="agenda.autopilot.momentum.usa.top3000.medium",
            name="Momentum medium autopilot sweep",
            family=ResearchFamily.MOMENTUM,
            priority=0.6,
            target_region="USA",
            target_universe="TOP3000",
            target_horizons=["medium"],
            motivation="Probe continuation effects with conservative volatility-aware normalization and bounded operators.",
            constraints=["require_cross_sectional_normalization", "avoid_fragile_control_flow"],
            tags=["momentum", "medium", "autopilot"],
            owner="autopilot",
            status="backlog",
        )
    ]

    generated = generator.generate(
        existing_agendas=existing,
        queue_depth=0,
        learner_summaries=[],
        recent_failed_families=[],
    )

    assert generated
    assert all(agenda_dedupe_key(agenda) != agenda_dedupe_key(existing[0]) for agenda in generated)


def test_hybrid_agenda_generator_uses_llm_when_queue_is_low():
    llm_agenda = ResearchAgenda(
        agenda_id="agenda.autollm.001",
        name="LLM generated revision drift agenda",
        family=ResearchFamily.REVISION_DRIFT,
        priority=0.72,
        target_region="USA",
        target_universe="TOP3000",
        target_horizons=["medium"],
        motivation="Probe revision drift under conservative normalization and bounded operators.",
        constraints=["require_cross_sectional_normalization"],
        tags=["revision_drift", "medium", "autopilot"],
        owner="autopilot_llm",
        status="backlog",
    )
    learner_summary = FamilyLearnerSummary(
        family=ResearchFamily.REVISION_DRIFT,
        total_candidates=8,
        simulation_candidate_count=4,
        critique_pass_rate=0.5,
        stage_a_pass_rate=0.5,
        simulation_timeout_rate=0.0,
        submission_ready_rate=0.25,
        median_stage_a_sharpe=1.1,
        latest_run_id="simulate.revision_drift.001",
        updated_at=datetime(2026, 1, 20, tzinfo=timezone.utc),
    )
    llm_client = _StubStructuredLLMClient([llm_agenda])
    generator = HybridAgendaGenerator(
        TemplateAgendaGenerator(enabled_families=[ResearchFamily.MOMENTUM]),
        LLMAgendaAugmentor(
            llm_client,
            target_region="USA",
            target_universe="TOP3000",
            enabled_families=[ResearchFamily.REVISION_DRIFT],
        ),
        min_queue_depth=5,
    )

    generated = generator.generate(
        existing_agendas=[],
        queue_depth=1,
        learner_summaries=[learner_summary],
        recent_failed_families=[],
    )

    assert any(agenda.agenda_id == "agenda.autollm.001" for agenda in generated)
    assert llm_client.calls == 1
    assert generator.last_summary["llm_generated_count"] == 1
