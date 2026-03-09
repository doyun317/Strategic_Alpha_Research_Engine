import pytest
from pydantic import ValidationError

from strategic_alpha_engine.domain.enums import ResearchHorizon
from strategic_alpha_engine.domain.examples import build_sample_research_agenda
from strategic_alpha_engine.domain.research_agenda import ResearchAgenda


def test_research_agenda_builds_valid_sample():
    agenda = build_sample_research_agenda()

    assert agenda.family == "quality_deterioration"
    assert agenda.target_horizons == ["medium"]


def test_research_agenda_rejects_duplicate_horizons():
    payload = build_sample_research_agenda().model_dump()
    payload["target_horizons"] = [ResearchHorizon.MEDIUM, ResearchHorizon.MEDIUM]

    with pytest.raises(ValidationError):
        ResearchAgenda(**payload)

