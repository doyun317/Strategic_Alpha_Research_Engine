import pytest

from strategic_alpha_engine.application.services import (
    MetadataBackedStaticValidator,
    SkeletonCandidateSynthesizer,
)
from strategic_alpha_engine.application.workflows import SynthesizeWorkflow
from strategic_alpha_engine.domain.examples import build_sample_hypothesis_spec, build_sample_signal_blueprint
from strategic_alpha_engine.infrastructure.metadata import load_seed_metadata_catalog
from strategic_alpha_engine.testing import SampleStrategicCritic


def test_synthesize_workflow_produces_evaluations():
    workflow = SynthesizeWorkflow(
        candidate_synthesizer=SkeletonCandidateSynthesizer(),
        static_validator=MetadataBackedStaticValidator(load_seed_metadata_catalog()),
        strategic_critic=SampleStrategicCritic(),
    )

    result = workflow.run(
        hypothesis=build_sample_hypothesis_spec(),
        blueprint=build_sample_signal_blueprint(),
    )

    assert len(result.evaluations) == result.blueprint.target_expression_count
    assert all(evaluation.validation.passes is True for evaluation in result.evaluations)


def test_synthesize_workflow_rejects_mismatched_hypothesis_and_blueprint():
    workflow = SynthesizeWorkflow(
        candidate_synthesizer=SkeletonCandidateSynthesizer(),
        static_validator=MetadataBackedStaticValidator(load_seed_metadata_catalog()),
        strategic_critic=SampleStrategicCritic(),
    )
    hypothesis = build_sample_hypothesis_spec().model_copy(update={"hypothesis_id": "hyp.other.001"})

    with pytest.raises(ValueError, match="blueprint.hypothesis_id must match hypothesis.hypothesis_id"):
        workflow.run(
            hypothesis=hypothesis,
            blueprint=build_sample_signal_blueprint(),
        )
