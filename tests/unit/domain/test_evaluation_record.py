from datetime import datetime, timezone

import pytest

from strategic_alpha_engine.domain import EvaluationRecord, build_sample_evaluation_record


def test_evaluation_record_accepts_valid_stage_a_payload():
    record = build_sample_evaluation_record()

    assert record.evaluation_stage == "stage_a"
    assert record.pass_decision is True
    assert record.period == "P1Y0M0D"


def test_evaluation_record_rejects_true_pass_decision_for_failed_status():
    payload = build_sample_evaluation_record().model_dump(mode="python")
    payload.update(
        {
            "status": "failed",
            "pass_decision": True,
            "evaluated_at": datetime(2026, 1, 15, 14, 42, tzinfo=timezone.utc),
        }
    )

    with pytest.raises(
        ValueError,
        match="pass_decision can only be true when simulation status succeeded",
    ):
        EvaluationRecord(**payload)
