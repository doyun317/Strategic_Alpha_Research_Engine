from strategic_alpha_engine.application.services.skeleton_synthesizer import SkeletonCandidateSynthesizer
from strategic_alpha_engine.domain.examples import build_sample_signal_blueprint


def test_skeleton_synthesizer_produces_candidates():
    blueprint = build_sample_signal_blueprint()
    synthesizer = SkeletonCandidateSynthesizer()

    candidates = synthesizer.synthesize(blueprint)

    assert len(candidates) == blueprint.target_expression_count
    assert all(candidate.generation_method == "skeleton_fill" for candidate in candidates)
    assert all(candidate.outer_normalization_present for candidate in candidates)

