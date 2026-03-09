from datetime import datetime, timezone

from strategic_alpha_engine.application.contracts import FamilyLearnerSummary
from strategic_alpha_engine.application.services import (
    FamilyWeightedAgendaPrioritizer,
    HeuristicSearchPolicyLearner,
)
from strategic_alpha_engine.domain.enums import ResearchFamily
from strategic_alpha_engine.domain.research_agenda import ResearchAgenda


def test_heuristic_search_policy_learner_ranks_families_by_explore_exploit_balance():
    summaries = [
        FamilyLearnerSummary(
            family=ResearchFamily.QUALITY_DETERIORATION,
            total_candidates=8,
            simulation_candidate_count=4,
            critique_pass_rate=0.9,
            stage_a_pass_rate=0.8,
            simulation_timeout_rate=0.0,
            submission_ready_rate=0.0,
            median_stage_a_sharpe=1.3,
            latest_run_id="run.quality.001",
            updated_at=datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc),
        ),
        FamilyLearnerSummary(
            family=ResearchFamily.MOMENTUM,
            total_candidates=3,
            simulation_candidate_count=1,
            critique_pass_rate=0.55,
            stage_a_pass_rate=0.5,
            simulation_timeout_rate=0.0,
            submission_ready_rate=0.0,
            median_stage_a_sharpe=0.8,
            latest_run_id="run.momentum.001",
            updated_at=datetime(2026, 3, 1, 12, 5, tzinfo=timezone.utc),
        ),
        FamilyLearnerSummary(
            family=ResearchFamily.LIQUIDITY_STRESS,
            total_candidates=5,
            simulation_candidate_count=4,
            critique_pass_rate=0.35,
            stage_a_pass_rate=0.25,
            simulation_timeout_rate=0.5,
            submission_ready_rate=0.0,
            median_stage_a_sharpe=0.4,
            latest_run_id="run.liquidity.001",
            updated_at=datetime(2026, 3, 1, 12, 10, tzinfo=timezone.utc),
        ),
    ]

    recommendations = HeuristicSearchPolicyLearner().recommend(summaries)

    assert [recommendation.rank for recommendation in recommendations] == [1, 2, 3]
    assert recommendations[0].family == ResearchFamily.QUALITY_DETERIORATION
    assert recommendations[1].family == ResearchFamily.MOMENTUM
    assert recommendations[2].family == ResearchFamily.LIQUIDITY_STRESS
    assert "underexplored_family" in recommendations[1].reasons
    assert "timeout_penalty_applied" in recommendations[2].reasons


def test_family_weighted_agenda_prioritizer_combines_base_priority_and_family_score():
    family_recommendations = HeuristicSearchPolicyLearner().recommend(
        [
            FamilyLearnerSummary(
                family=ResearchFamily.QUALITY_DETERIORATION,
                total_candidates=6,
                simulation_candidate_count=3,
                critique_pass_rate=0.9,
                stage_a_pass_rate=0.8,
                simulation_timeout_rate=0.0,
                submission_ready_rate=0.0,
                median_stage_a_sharpe=1.2,
                latest_run_id="run.quality.001",
                updated_at=datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc),
            ),
            FamilyLearnerSummary(
                family=ResearchFamily.MOMENTUM,
                total_candidates=3,
                simulation_candidate_count=1,
                critique_pass_rate=0.4,
                stage_a_pass_rate=0.4,
                simulation_timeout_rate=0.1,
                submission_ready_rate=0.0,
                median_stage_a_sharpe=0.6,
                latest_run_id="run.momentum.001",
                updated_at=datetime(2026, 3, 1, 12, 5, tzinfo=timezone.utc),
            ),
        ]
    )
    agendas = [
        ResearchAgenda(
            agenda_id="agenda.quality_deterioration.010",
            name="Quality deterioration follow-up",
            family=ResearchFamily.QUALITY_DETERIORATION,
            priority=0.6,
            target_region="USA",
            target_universe="TOP3000",
            target_horizons=["medium"],
            motivation="Extend a strong family with another conservative variation.",
            constraints=[],
            tags=["quality"],
            owner="system",
            status="active",
        ),
        ResearchAgenda(
            agenda_id="agenda.momentum.010",
            name="Momentum follow-up",
            family=ResearchFamily.MOMENTUM,
            priority=0.75,
            target_region="USA",
            target_universe="TOP3000",
            target_horizons=["medium"],
            motivation="Keep momentum on the queue with lower family conviction.",
            constraints=[],
            tags=["momentum"],
            owner="system",
            status="active",
        ),
    ]

    recommendations = FamilyWeightedAgendaPrioritizer().prioritize(agendas, family_recommendations)

    assert recommendations[0].agenda_id == "agenda.quality_deterioration.010"
    assert recommendations[0].adjusted_priority > recommendations[1].adjusted_priority
    assert "family_score=" in recommendations[0].reasons[1]
