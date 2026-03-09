from datetime import datetime, timezone

import pytest

from strategic_alpha_engine.domain import ValidationRecord, build_sample_validation_record


def test_validation_record_accepts_valid_stage_b_payload():
    record = build_sample_validation_record()

    assert record.validation_stage == "stage_b"
    assert record.pass_decision is True
    assert record.period == "P3Y0M0D"


def test_validation_record_rejects_true_pass_decision_for_failed_status():
    payload = build_sample_validation_record().model_dump(mode="python")
    payload.update(
        {
            "status": "failed",
            "pass_decision": True,
            "validated_at": datetime(2026, 1, 18, 10, 30, tzinfo=timezone.utc),
        }
    )

    with pytest.raises(
        ValueError,
        match="pass_decision can only be true when validation status succeeded",
    ):
        ValidationRecord(**payload)
