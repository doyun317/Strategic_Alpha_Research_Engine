import pytest

from strategic_alpha_engine.domain import PromotionDecision, build_sample_promotion_decision


def test_promotion_decision_accepts_valid_stage_a_promotion():
    decision = build_sample_promotion_decision()

    assert decision.decision == "promote"
    assert decision.to_stage == "sim_passed"


def test_promotion_decision_rejects_invalid_reject_target():
    payload = build_sample_promotion_decision().model_dump(mode="python")
    payload.update(
        {
            "decision": "reject",
            "to_stage": "sim_passed",
        }
    )

    with pytest.raises(
        ValueError,
        match="reject decisions must move the candidate to rejected",
    ):
        PromotionDecision(**payload)
