from __future__ import annotations

from strategic_alpha_engine.application.services.interfaces import AgendaPrioritizer, ResearchAgendaManager
from strategic_alpha_engine.domain.research_agenda import ResearchAgenda
from strategic_alpha_engine.domain.search_policy import (
    AgendaSelection,
    FamilyPolicyRecommendation,
)


class HeuristicResearchAgendaManager(ResearchAgendaManager):
    def __init__(
        self,
        agenda_prioritizer: AgendaPrioritizer,
    ):
        self.agenda_prioritizer = agenda_prioritizer

    def select_next(
        self,
        agendas: list[ResearchAgenda],
        family_recommendations: list[FamilyPolicyRecommendation],
        *,
        excluded_agenda_ids: set[str] | None = None,
    ) -> AgendaSelection:
        excluded_agenda_ids = excluded_agenda_ids or set()
        eligible_agendas = [
            agenda
            for agenda in agendas
            if agenda.status in {"active", "backlog"}
        ]
        prioritized = self.agenda_prioritizer.prioritize(
            eligible_agendas,
            family_recommendations,
        )
        agendas_by_id = {agenda.agenda_id: agenda for agenda in eligible_agendas}

        selected_agenda = None
        for recommendation in prioritized:
            agenda = agendas_by_id[recommendation.agenda_id]
            if agenda.agenda_id in excluded_agenda_ids:
                continue
            selected_agenda = agenda
            break

        return AgendaSelection(
            selected_agenda=selected_agenda,
            agenda_recommendations=prioritized,
            excluded_agenda_ids=sorted(excluded_agenda_ids),
        )
