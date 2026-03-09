from __future__ import annotations

from strategic_alpha_engine.application.contracts import FamilyLearnerSummary
from strategic_alpha_engine.application.services.interfaces import AgendaPrioritizer, SearchPolicyLearner
from strategic_alpha_engine.domain.research_agenda import ResearchAgenda
from strategic_alpha_engine.domain.search_policy import (
    AgendaPriorityRecommendation,
    FamilyPolicyRecommendation,
)


class HeuristicSearchPolicyLearner(SearchPolicyLearner):
    def recommend(
        self,
        summaries: list[FamilyLearnerSummary],
    ) -> list[FamilyPolicyRecommendation]:
        recommendations: list[FamilyPolicyRecommendation] = []

        for summary in summaries:
            normalized_sharpe = self._normalize_sharpe(summary.median_stage_a_sharpe)
            exploit_score = self._clamp(
                (0.45 * summary.stage_a_pass_rate)
                + (0.25 * summary.critique_pass_rate)
                + (0.30 * normalized_sharpe)
            )
            exploration_bonus = self._clamp(1.0 - min(summary.simulation_candidate_count, 12) / 12)
            risk_penalty = self._clamp(
                (0.70 * summary.simulation_timeout_rate)
                + (0.30 * max(0.0, 1.0 - summary.stage_a_pass_rate))
            )
            final_score = self._clamp(
                (0.60 * exploit_score)
                + (0.25 * exploration_bonus)
                + (0.15 * summary.submission_ready_rate)
                - (0.35 * risk_penalty)
            )

            reasons: list[str] = []
            if summary.simulation_candidate_count <= 2:
                reasons.append("underexplored_family")
            if summary.stage_a_pass_rate >= 0.6:
                reasons.append("strong_stage_a_conversion")
            if normalized_sharpe >= 0.6:
                reasons.append("high_median_stage_a_sharpe")
            if summary.simulation_timeout_rate >= 0.25:
                reasons.append("timeout_penalty_applied")
            if not reasons:
                reasons.append("balanced_explore_exploit_mix")

            recommendations.append(
                FamilyPolicyRecommendation(
                    family=summary.family,
                    rank=1,
                    final_score=round(final_score, 4),
                    exploit_score=round(exploit_score, 4),
                    exploration_bonus=round(exploration_bonus, 4),
                    risk_penalty=round(risk_penalty, 4),
                    reasons=reasons,
                    latest_run_id=summary.latest_run_id,
                    updated_at=summary.updated_at,
                )
            )

        recommendations.sort(
            key=lambda recommendation: (
                recommendation.final_score,
                recommendation.exploit_score,
                recommendation.exploration_bonus,
            ),
            reverse=True,
        )

        return [
            recommendation.model_copy(update={"rank": rank})
            for rank, recommendation in enumerate(recommendations, start=1)
        ]

    def _normalize_sharpe(self, value: float | None) -> float:
        if value is None:
            return 0.0
        return self._clamp(min(value, 2.0) / 2.0)

    def _clamp(self, value: float) -> float:
        return max(0.0, min(1.0, value))


class FamilyWeightedAgendaPrioritizer(AgendaPrioritizer):
    def prioritize(
        self,
        agendas: list[ResearchAgenda],
        family_recommendations: list[FamilyPolicyRecommendation],
    ) -> list[AgendaPriorityRecommendation]:
        recommendations_by_family = {
            recommendation.family: recommendation
            for recommendation in family_recommendations
        }
        prioritized: list[AgendaPriorityRecommendation] = []

        for agenda in agendas:
            family_recommendation = recommendations_by_family.get(agenda.family)
            family_score = family_recommendation.final_score if family_recommendation is not None else 0.5
            adjusted_priority = self._clamp((0.40 * agenda.priority) + (0.60 * family_score))
            reasons = [
                f"base_priority={round(agenda.priority, 4)}",
                f"family_score={round(family_score, 4)}",
            ]
            if family_recommendation is not None:
                reasons.extend(family_recommendation.reasons[:3])
            else:
                reasons.append("no_family_history_default_weight")

            prioritized.append(
                AgendaPriorityRecommendation(
                    agenda_id=agenda.agenda_id,
                    family=agenda.family,
                    agenda_name=agenda.name,
                    base_priority=round(agenda.priority, 4),
                    family_score=round(family_score, 4),
                    adjusted_priority=round(adjusted_priority, 4),
                    priority_delta=round(adjusted_priority - agenda.priority, 4),
                    reasons=reasons,
                )
            )

        prioritized.sort(
            key=lambda recommendation: (
                recommendation.adjusted_priority,
                recommendation.family_score,
                recommendation.base_priority,
            ),
            reverse=True,
        )
        return prioritized

    def _clamp(self, value: float) -> float:
        return max(0.0, min(1.0, value))
