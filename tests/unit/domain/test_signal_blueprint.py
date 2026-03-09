import pytest
from pydantic import ValidationError

from strategic_alpha_engine.domain import build_sample_signal_blueprint
from strategic_alpha_engine.domain.enums import NormalizationKind, NormalizationTarget
from strategic_alpha_engine.domain.signal_blueprint import NormalizationSpec, SignalBlueprint


def test_signal_blueprint_builds_valid_sample():
    blueprint = build_sample_signal_blueprint()

    assert blueprint.blueprint_id == "bp.quality_deterioration.001"
    assert blueprint.primary_fields == ["cashflow_op", "debt_lt"]
    assert blueprint.operator_policy.require_outer_normalization is True


def test_signal_blueprint_rejects_unknown_primary_field():
    payload = build_sample_signal_blueprint().model_dump()
    payload["primary_fields"] = ["cashflow_op", "missing_field"]

    with pytest.raises(ValidationError):
        SignalBlueprint(**payload)


def test_signal_blueprint_rejects_short_temporal_lookback_on_slow_fields():
    payload = build_sample_signal_blueprint().model_dump()
    payload["transform_plan"][0]["lookback_days"] = 5

    with pytest.raises(ValidationError):
        SignalBlueprint(**payload)


def test_signal_blueprint_requires_final_cross_sectional_normalization_when_enabled():
    payload = build_sample_signal_blueprint().model_dump()
    payload["normalization_plan"] = [
        NormalizationSpec(
            kind=NormalizationKind.TIME_SERIES_ZSCORE,
            target=NormalizationTarget.SUBSIGNAL,
            rationale="Only sub-signal normalization remains.",
        ).model_dump()
    ]

    with pytest.raises(ValidationError):
        SignalBlueprint(**payload)
