from strategic_alpha_engine.application.services.rule_based_critic import RuleBasedStrategicCritic
from strategic_alpha_engine.domain.examples import (
    build_sample_expression_candidate,
    build_sample_hypothesis_spec,
    build_sample_signal_blueprint,
)


def test_rule_based_critic_accepts_valid_sample_candidate():
    critic = RuleBasedStrategicCritic()

    report = critic.critique(
        build_sample_hypothesis_spec(),
        build_sample_signal_blueprint(),
        build_sample_expression_candidate(),
    )

    assert report.passes is True
    assert report.overall_score > 0.7


def test_rule_based_critic_rejects_missing_outer_rank():
    critic = RuleBasedStrategicCritic()
    candidate = build_sample_expression_candidate().model_copy(
        update={"expression": "divide(subtract(cashflow_op, debt_lt), add(abs(debt_lt), 0.01))"}
    )

    report = critic.critique(
        build_sample_hypothesis_spec(),
        build_sample_signal_blueprint(),
        candidate,
    )

    assert report.passes is False
    assert any(issue.code == "missing_outer_rank" for issue in report.issues)

