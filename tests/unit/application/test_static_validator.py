from strategic_alpha_engine.application.services.static_validator import MetadataBackedStaticValidator
from strategic_alpha_engine.domain.examples import build_sample_expression_candidate, build_sample_signal_blueprint
from strategic_alpha_engine.infrastructure.metadata import load_seed_metadata_catalog


def test_static_validator_accepts_valid_sample_candidate():
    validator = MetadataBackedStaticValidator(load_seed_metadata_catalog())

    report = validator.validate(build_sample_signal_blueprint(), build_sample_expression_candidate())

    assert report.passes is True
    assert report.checked_operator_count >= 1
    assert report.checked_field_count == 2


def test_static_validator_rejects_unknown_operator():
    validator = MetadataBackedStaticValidator(load_seed_metadata_catalog())
    candidate = build_sample_expression_candidate().model_copy(
        update={"expression": "rank(foo(cashflow_op))"}
    )

    report = validator.validate(build_sample_signal_blueprint(), candidate)

    assert report.passes is False
    assert any(issue.code == "unknown_operator" for issue in report.issues)


def test_static_validator_rejects_unknown_field():
    validator = MetadataBackedStaticValidator(load_seed_metadata_catalog())
    candidate = build_sample_expression_candidate().model_copy(
        update={"expression": "rank(divide(cashflow_unknown, add(abs(debt_lt), 0.01)))"}
    )

    report = validator.validate(build_sample_signal_blueprint(), candidate)

    assert report.passes is False
    assert any(issue.code == "unknown_field" for issue in report.issues)


def test_static_validator_rejects_invalid_operator_arity():
    validator = MetadataBackedStaticValidator(load_seed_metadata_catalog())
    candidate = build_sample_expression_candidate().model_copy(
        update={"expression": "rank(divide(cashflow_op, debt_lt, close))"}
    )

    report = validator.validate(build_sample_signal_blueprint(), candidate)

    assert report.passes is False
    assert any(issue.code == "invalid_operator_arity" for issue in report.issues)
