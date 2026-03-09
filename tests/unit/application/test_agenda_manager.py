from datetime import datetime, timezone

from strategic_alpha_engine.application.services import (
    FamilyWeightedAgendaPrioritizer,
    HeuristicResearchAgendaManager,
)
from strategic_alpha_engine.domain.enums import ResearchFamily, ResearchHorizon
from strategic_alpha_engine.domain.research_agenda import ResearchAgenda
from strategic_alpha_engine.domain.search_policy import FamilyPolicyRecommendation


def test_heuristic_research_agenda_manager_selects_highest_eligible_agenda():
    agendas = [
        ResearchAgenda(
            agenda_id="agenda.quality_deterioration.001",
            name="Quality deterioration queue",
            family=ResearchFamily.QUALITY_DETERIORATION,
            priority=0.82,
            target_region="USA",
            target_universe="TOP3000",
            target_horizons=[ResearchHorizon.MEDIUM],
            motivation="Prioritize a strong quality deterioration branch.",
            constraints=[],
            tags=["quality"],
            owner="system",
            status="active",
        ),
        ResearchAgenda(
            agenda_id="agenda.momentum.001",
            name="Momentum queue",
            family=ResearchFamily.MOMENTUM,
            priority=0.75,
            target_region="USA",
            target_universe="TOP3000",
            target_horizons=[ResearchHorizon.MEDIUM],
            motivation="Secondary momentum branch for continuation ideas.",
            constraints=[],
            tags=["momentum"],
            owner="system",
            status="active",
        ),
        ResearchAgenda(
            agenda_id="agenda.liquidity_stress.001",
            name="Liquidity stress queue",
            family=ResearchFamily.LIQUIDITY_STRESS,
            priority=0.9,
            target_region="USA",
            target_universe="TOP3000",
            target_horizons=[ResearchHorizon.SHORT],
            motivation="This branch is paused and should not be selected.",
            constraints=[],
            tags=["liquidity"],
            owner="system",
            status="paused",
        ),
    ]
    family_recommendations = [
        FamilyPolicyRecommendation(
            family=ResearchFamily.QUALITY_DETERIORATION,
            rank=1,
            final_score=0.78,
            exploit_score=0.8,
            exploration_bonus=0.6,
            risk_penalty=0.1,
            reasons=["strong_stage_a_conversion"],
            latest_run_id="run.quality.001",
            updated_at=datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc),
        ),
        FamilyPolicyRecommendation(
            family=ResearchFamily.MOMENTUM,
            rank=2,
            final_score=0.58,
            exploit_score=0.55,
            exploration_bonus=0.65,
            risk_penalty=0.15,
            reasons=["underexplored_family"],
            latest_run_id="run.momentum.001",
            updated_at=datetime(2026, 3, 1, 12, 5, tzinfo=timezone.utc),
        ),
    ]

    selection = HeuristicResearchAgendaManager(
        agenda_prioritizer=FamilyWeightedAgendaPrioritizer(),
    ).select_next(
        agendas,
        family_recommendations,
        excluded_agenda_ids={"agenda.quality_deterioration.001"},
    )

    assert selection.selected_agenda is not None
    assert selection.selected_agenda.agenda_id == "agenda.momentum.001"
    assert selection.agenda_recommendations[0].agenda_id == "agenda.quality_deterioration.001"
    assert selection.excluded_agenda_ids == ["agenda.quality_deterioration.001"]
