from datetime import datetime, timezone

from strategic_alpha_engine.application.services import RuleBasedValidationRunner
from strategic_alpha_engine.application.workflows import ValidateWorkflow
from strategic_alpha_engine.domain.enums import ValidationStage
from strategic_alpha_engine.domain.examples import (
    build_sample_expression_candidate,
    build_sample_hypothesis_spec,
    build_sample_signal_blueprint,
)


def test_validate_workflow_builds_validation_records_for_selected_candidates():
    candidate_a = build_sample_expression_candidate().model_copy(
        update={"candidate_id": "cand.validation.001"}
    )
    candidate_b = build_sample_expression_candidate().model_copy(
        update={"candidate_id": "cand.validation.002"}
    )
    workflow = ValidateWorkflow(
        validation_runner=RuleBasedValidationRunner(
            base_time=datetime(2026, 1, 18, 10, 30, tzinfo=timezone.utc)
        )
    )

    result = workflow.run(
        source_run_id="validate.quality_deterioration.001",
        candidate_source_run_id="simulate.quality_deterioration.001",
        hypothesis=build_sample_hypothesis_spec(),
        blueprint=build_sample_signal_blueprint(),
        candidates=[candidate_a, candidate_b],
        validation_stage=ValidationStage.STAGE_B,
        period="P3Y0M0D",
    )

    assert result.validated_candidate_ids == [
        "cand.validation.001",
        "cand.validation.002",
    ]
    assert result.passed_candidate_ids == result.validated_candidate_ids
    assert result.failed_candidate_ids == []
    assert result.outcomes[0].validation.candidate_source_run_id == "simulate.quality_deterioration.001"
    assert result.outcomes[0].validation.validation_stage == ValidationStage.STAGE_B
