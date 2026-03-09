from datetime import datetime, timezone

from strategic_alpha_engine.domain.enums import (
    ExpectedDirection,
    EvaluationStage,
    FieldClass,
    FieldRole,
    NormalizationKind,
    NormalizationTarget,
    PromotionDecisionKind,
    ResearchFamily,
    ResearchHorizon,
    RiskControlKind,
    TransformKind,
    UpdateCadence,
)
from strategic_alpha_engine.domain.evaluation import EvaluationRecord
from strategic_alpha_engine.domain.expression_candidate import ExpressionCandidate
from strategic_alpha_engine.domain.hypothesis_spec import HypothesisSpec
from strategic_alpha_engine.domain.critique_report import CritiqueIssue, CritiqueReport
from strategic_alpha_engine.domain.promotion import PromotionDecision
from strategic_alpha_engine.domain.research_agenda import ResearchAgenda
from strategic_alpha_engine.domain.simulation import SimulationRequest, SimulationRun
from strategic_alpha_engine.domain.signal_blueprint import (
    FieldSelection,
    NormalizationSpec,
    OperatorPolicy,
    RiskControlSpec,
    SignalBlueprint,
    SkeletonTemplate,
    TransformSpec,
)


def build_sample_research_agenda() -> ResearchAgenda:
    return ResearchAgenda(
        agenda_id="agenda.quality_deterioration.001",
        name="Medium-horizon quality deterioration",
        family=ResearchFamily.QUALITY_DETERIORATION,
        priority=0.8,
        target_region="USA",
        target_universe="TOP3000",
        target_horizons=[ResearchHorizon.MEDIUM],
        motivation=(
            "Explore firms where leverage worsens while cash generation deteriorates, "
            "with conservative normalization and low structural risk."
        ),
        constraints=["require_cross_sectional_normalization", "avoid_short_delay_on_fundamentals"],
        tags=["quality", "fundamental", "medium_horizon"],
        owner="system",
        status="active",
    )


def build_sample_hypothesis_spec() -> HypothesisSpec:
    return HypothesisSpec(
        hypothesis_id="hyp.quality_deterioration.001",
        agenda_id="agenda.quality_deterioration.001",
        family=ResearchFamily.QUALITY_DETERIORATION,
        thesis_name="Leverage up, cash generation down",
        economic_rationale=(
            "Firms showing rising leverage while operating cash generation weakens "
            "tend to underperform over a medium horizon."
        ),
        expected_direction=ExpectedDirection.LOWER_SIGNAL_OUTPERFORMS,
        horizon=ResearchHorizon.MEDIUM,
        target_region="USA",
        target_universe="TOP3000",
        market_context="Cross-sectional equity alpha in liquid US names.",
        field_classes=[FieldClass.FUNDAMENTAL, FieldClass.PRICE],
        preferred_update_cadences=[UpdateCadence.QUARTERLY, UpdateCadence.DAILY],
        risk_notes=["Require cross-sectional normalization", "Avoid raw level domination"],
        evidence_requirements=["Positive medium-horizon Sharpe", "Stable turnover band"],
        forbidden_patterns=["short_delay_on_slow_fundamentals", "raw_level_only"],
        confidence=0.68,
        author="system",
    )


def build_sample_signal_blueprint() -> SignalBlueprint:
    return SignalBlueprint(
        blueprint_id="bp.quality_deterioration.001",
        hypothesis_id="hyp.quality_deterioration.001",
        summary="Use medium-horizon deterioration in fundamentals with final cross-sectional rank.",
        expression_intent="Capture worsening cash generation versus leverage using safe normalization.",
        field_selections=[
            FieldSelection(
                field_id="cashflow_op",
                field_class=FieldClass.FUNDAMENTAL,
                update_cadence=UpdateCadence.QUARTERLY,
                role=FieldRole.PRIMARY_SIGNAL,
                rationale="Operating cashflow deterioration is the core quality signal.",
            ),
            FieldSelection(
                field_id="debt_lt",
                field_class=FieldClass.FUNDAMENTAL,
                update_cadence=UpdateCadence.QUARTERLY,
                role=FieldRole.DENOMINATOR_SCALE,
                rationale="Long-term debt tracks leverage deterioration.",
            ),
            FieldSelection(
                field_id="close",
                field_class=FieldClass.PRICE,
                update_cadence=UpdateCadence.DAILY,
                role=FieldRole.CONFIRMATION,
                rationale="Price-based ranking stabilizes cross-sectional comparability.",
            ),
        ],
        primary_fields=["cashflow_op", "debt_lt"],
        secondary_fields=["close"],
        transform_plan=[
            TransformSpec(
                name="cashflow_medium_delta",
                kind=TransformKind.DELTA,
                input_fields=["cashflow_op"],
                lookback_days=63,
                rationale="Quarter-over-quarter style change proxy.",
            ),
            TransformSpec(
                name="debt_medium_delta",
                kind=TransformKind.DELTA,
                input_fields=["debt_lt"],
                lookback_days=63,
                rationale="Capture leverage build-up over a comparable horizon.",
            ),
            TransformSpec(
                name="quality_spread",
                kind=TransformKind.SPREAD,
                input_fields=["cashflow_op", "debt_lt"],
                rationale="Express weakening cashflow relative to leverage.",
            ),
        ],
        normalization_plan=[
            NormalizationSpec(
                kind=NormalizationKind.CROSS_SECTIONAL_RANK,
                target=NormalizationTarget.FINAL_EXPRESSION,
                rationale="Final cross-sectional rank reduces outlier domination.",
            )
        ],
        risk_control_plan=[
            RiskControlSpec(
                kind=RiskControlKind.OUTLIER_CONTROL,
                parameters={"method": "rank"},
                rationale="Use normalization-based outlier control.",
            ),
            RiskControlSpec(
                kind=RiskControlKind.DENOMINATOR_FLOOR,
                parameters={"epsilon": 0.01},
                rationale="Avoid unstable divisions when synthesizing formulas.",
            ),
        ],
        operator_policy=OperatorPolicy(
            allowed_operators=[
                "rank",
                "subtract",
                "divide",
                "add",
                "abs",
                "ts_delta",
            ],
            forbidden_operators=["ts_sum", "group_backfill"],
            max_operator_count=6,
            max_nesting_depth=4,
            require_explicit_lookbacks=True,
            require_outer_normalization=True,
        ),
        skeleton_templates=[
            SkeletonTemplate(
                template_id="skel.rank_spread.001",
                name="ranked_quality_spread",
                template="rank(divide(subtract(FIELD_A, FIELD_B), add(abs(FIELD_B), CONST_EPS)))",
                slot_names=["FIELD_A", "FIELD_B", "CONST_EPS"],
                rationale="Safe ratio-style spread with final normalization.",
            )
        ],
        disallowed_patterns=["short_delay_on_slow_fundamentals", "missing_outer_rank"],
        target_expression_count=4,
        notes="Blueprint is intentionally conservative for the first synthesis pass.",
    )


def build_sample_expression_candidate() -> ExpressionCandidate:
    return ExpressionCandidate(
        candidate_id="cand.quality_deterioration.001",
        blueprint_id="bp.quality_deterioration.001",
        hypothesis_id="hyp.quality_deterioration.001",
        expression="rank(divide(subtract(cashflow_op, debt_lt), add(abs(debt_lt), 0.01)))",
        generation_method="skeleton_fill",
        skeleton_template_id="skel.rank_spread.001",
        placeholder_bindings={
            "FIELD_A": "cashflow_op",
            "FIELD_B": "debt_lt",
            "CONST_EPS": 0.01,
        },
    )


def build_sample_critique_report() -> CritiqueReport:
    return CritiqueReport(
        critique_id="critique.quality_deterioration.001",
        candidate_id="cand.quality_deterioration.001",
        blueprint_id="bp.quality_deterioration.001",
        passes=True,
        overall_score=0.88,
        structural_quality_score=0.9,
        economic_coherence_score=0.86,
        data_horizon_alignment_score=0.88,
        issues=[
            CritiqueIssue(
                code="conservative_signal",
                severity="low",
                message="Signal is conservative and may have modest spread.",
                suggestion="Consider a complementary confirmation term if differentiation is weak.",
            )
        ],
        repair_suggestions=["Optionally add a confirmation term from price momentum."],
        tags=["sample", "quality"],
    )


def build_sample_simulation_request() -> SimulationRequest:
    candidate = build_sample_expression_candidate()
    return SimulationRequest(
        simulation_request_id="simreq.quality_deterioration.001",
        candidate_id=candidate.candidate_id,
        hypothesis_id=candidate.hypothesis_id,
        blueprint_id=candidate.blueprint_id,
        expression=candidate.expression,
        region="USA",
        universe="TOP3000",
        delay=1,
        neutralization="subindustry",
        test_period="P1Y0M0D",
    )


def build_sample_simulation_run() -> SimulationRun:
    submitted_at = datetime(2026, 1, 15, 14, 30, tzinfo=timezone.utc)
    completed_at = datetime(2026, 1, 15, 14, 42, tzinfo=timezone.utc)
    return SimulationRun.from_request(
        simulation_run_id="simrun.quality_deterioration.001",
        request=build_sample_simulation_request(),
    ).mark_submitted(
        provider_run_id="brain.run.quality_deterioration.001",
        submitted_at=submitted_at,
    ).mark_running().mark_succeeded(completed_at=completed_at)


def build_sample_evaluation_record() -> EvaluationRecord:
    request = build_sample_simulation_request()
    run = build_sample_simulation_run()
    return EvaluationRecord(
        evaluation_id="eval.quality_deterioration.001.stage_a",
        candidate_id=request.candidate_id,
        hypothesis_id=request.hypothesis_id,
        blueprint_id=request.blueprint_id,
        simulation_request_id=request.simulation_request_id,
        simulation_run_id=run.simulation_run_id,
        source_run_id="simulate.quality_deterioration.001",
        evaluation_stage=EvaluationStage.STAGE_A,
        period=request.test_period,
        status=run.status,
        sharpe=1.21,
        fitness=1.05,
        turnover=0.17,
        returns=0.14,
        drawdown=0.06,
        checks=["delay_ok", "neutralization_ok"],
        grade="A",
        pass_decision=True,
        reasons=["meets_stage_a_thresholds"],
        evaluated_at=datetime(2026, 1, 15, 14, 42, tzinfo=timezone.utc),
    )


def build_sample_promotion_decision() -> PromotionDecision:
    evaluation = build_sample_evaluation_record()
    return PromotionDecision(
        promotion_id="promotion.quality_deterioration.001.stage_a",
        candidate_id=evaluation.candidate_id,
        hypothesis_id=evaluation.hypothesis_id,
        blueprint_id=evaluation.blueprint_id,
        evaluation_id=evaluation.evaluation_id,
        source_run_id=evaluation.source_run_id,
        from_stage="critique_passed",
        to_stage="sim_passed",
        decision=PromotionDecisionKind.PROMOTE,
        reasons=["stage_a_passed"],
        decided_at=evaluation.evaluated_at,
    )
