from strategic_alpha_engine.application.services import (
    MetadataBackedStaticValidator,
    SkeletonCandidateSynthesizer,
)
from strategic_alpha_engine.application.workflows import PlanWorkflow, SynthesizeWorkflow
from strategic_alpha_engine.domain import ExpressionCandidate, HypothesisSpec, ResearchAgenda, SignalBlueprint
from strategic_alpha_engine.domain.critique_report import CritiqueIssue, CritiqueReport
from strategic_alpha_engine.domain.examples import (
    build_sample_critique_report,
    build_sample_hypothesis_spec,
    build_sample_research_agenda,
    build_sample_signal_blueprint,
)
from strategic_alpha_engine.domain.signal_blueprint import SkeletonTemplate
from strategic_alpha_engine.infrastructure.metadata import load_seed_metadata_catalog


class SampleHypothesisPlanner:
    def plan(self, agenda: ResearchAgenda) -> HypothesisSpec:
        sample = build_sample_hypothesis_spec()
        return sample.model_copy(
            update={
                "agenda_id": agenda.agenda_id,
                "family": agenda.family,
                "horizon": agenda.target_horizons[0],
                "target_region": agenda.target_region,
                "target_universe": agenda.target_universe,
            }
        )


class SampleBlueprintBuilder:
    def build(self, hypothesis: HypothesisSpec) -> SignalBlueprint:
        sample = build_sample_signal_blueprint()
        skeleton_templates = list(sample.skeleton_templates)
        if len(skeleton_templates) == 1:
            skeleton_templates.append(
                SkeletonTemplate(
                    template_id="skel.rank_inverse.001",
                    name="ranked_inverse_leverage",
                    template="rank(divide(FIELD_A, add(abs(FIELD_B), CONST_EPS)))",
                    slot_names=["FIELD_A", "FIELD_B", "CONST_EPS"],
                    rationale="Conservative ratio form with final ranking.",
                )
            )
        return sample.model_copy(
            update={
                "hypothesis_id": hypothesis.hypothesis_id,
                "skeleton_templates": skeleton_templates,
            }
        )


class SampleStrategicCritic:
    def critique(
        self,
        hypothesis: HypothesisSpec,
        blueprint: SignalBlueprint,
        candidate: ExpressionCandidate,
    ) -> CritiqueReport:
        sample = build_sample_critique_report().model_copy(
            update={
                "critique_id": f"critique.{candidate.candidate_id}",
                "candidate_id": candidate.candidate_id,
                "blueprint_id": blueprint.blueprint_id,
                "critic_name": "sample_strategic_critic",
            }
        )
        if candidate.outer_normalization_present:
            return sample

        return sample.model_copy(
            update={
                "passes": False,
                "overall_score": 0.42,
                "structural_quality_score": 0.25,
                "issues": [
                    CritiqueIssue(
                        code="missing_outer_rank",
                        severity="high",
                        message="Final expression must include an outer rank normalization.",
                        suggestion="Wrap the final expression in rank().",
                    )
                ],
                "repair_suggestions": ["Wrap the final expression in rank()."],
            }
        )


def build_sample_plan_workflow() -> PlanWorkflow:
    return PlanWorkflow(
        hypothesis_planner=SampleHypothesisPlanner(),
        blueprint_builder=SampleBlueprintBuilder(),
    )


def build_sample_plan_result(agenda: ResearchAgenda | None = None):
    return build_sample_plan_workflow().run(agenda or build_sample_research_agenda())


def build_sample_synthesize_workflow() -> SynthesizeWorkflow:
    return SynthesizeWorkflow(
        candidate_synthesizer=SkeletonCandidateSynthesizer(),
        static_validator=MetadataBackedStaticValidator(load_seed_metadata_catalog()),
        strategic_critic=SampleStrategicCritic(),
    )


def build_sample_synthesize_result(plan_result=None):
    resolved_plan_result = plan_result or build_sample_plan_result()
    return build_sample_synthesize_workflow().run(
        hypothesis=resolved_plan_result.hypothesis,
        blueprint=resolved_plan_result.blueprint,
    )
