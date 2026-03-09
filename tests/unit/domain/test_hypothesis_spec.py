import pytest
from pydantic import ValidationError

from strategic_alpha_engine.domain import build_sample_hypothesis_spec
from strategic_alpha_engine.domain.enums import FieldClass, ResearchHorizon, UpdateCadence
from strategic_alpha_engine.domain.hypothesis_spec import HypothesisSpec


def test_hypothesis_spec_builds_valid_sample():
    hypothesis = build_sample_hypothesis_spec()

    assert hypothesis.hypothesis_id == "hyp.quality_deterioration.001"
    assert hypothesis.family == "quality_deterioration"
    assert hypothesis.field_classes == ["fundamental", "price"]


def test_hypothesis_spec_rejects_duplicate_field_classes():
    payload = build_sample_hypothesis_spec().model_dump()
    payload["field_classes"] = [FieldClass.FUNDAMENTAL, FieldClass.FUNDAMENTAL]

    with pytest.raises(ValidationError):
        HypothesisSpec(**payload)


def test_short_horizon_requires_fast_signal_or_cadence():
    payload = build_sample_hypothesis_spec().model_dump()
    payload["horizon"] = ResearchHorizon.SHORT
    payload["field_classes"] = [FieldClass.FUNDAMENTAL]
    payload["preferred_update_cadences"] = [UpdateCadence.QUARTERLY]

    with pytest.raises(ValidationError):
        HypothesisSpec(**payload)

