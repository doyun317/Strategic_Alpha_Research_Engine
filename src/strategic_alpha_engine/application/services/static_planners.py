from __future__ import annotations

from strategic_alpha_engine.domain.enums import (
    ExpectedDirection,
    FieldClass,
    FieldRole,
    NormalizationKind,
    NormalizationTarget,
    ResearchFamily,
    RiskControlKind,
    TransformKind,
    UpdateCadence,
)
from strategic_alpha_engine.domain.hypothesis_spec import HypothesisSpec
from strategic_alpha_engine.domain.research_agenda import ResearchAgenda
from strategic_alpha_engine.domain.signal_blueprint import (
    FieldSelection,
    NormalizationSpec,
    OperatorPolicy,
    RiskControlSpec,
    SignalBlueprint,
    SkeletonTemplate,
    TransformSpec,
)


class StaticHypothesisPlanner:
    def plan(self, agenda: ResearchAgenda) -> HypothesisSpec:
        horizon = agenda.target_horizons[0]

        if agenda.family == ResearchFamily.QUALITY_DETERIORATION:
            thesis_name = "Leverage rising while cash generation weakens"
            rationale = (
                "Firms with weakening operating cash generation relative to leverage "
                "tend to underperform on a medium horizon."
            )
            direction = ExpectedDirection.LOWER_SIGNAL_OUTPERFORMS
            field_classes = [FieldClass.FUNDAMENTAL, FieldClass.PRICE]
            cadences = [UpdateCadence.QUARTERLY, UpdateCadence.DAILY]
            forbidden_patterns = ["short_delay_on_slow_fundamentals", "raw_level_only"]
        elif agenda.family == ResearchFamily.MOMENTUM:
            thesis_name = "Intermediate price continuation with risk normalization"
            rationale = (
                "Recent continuation signals can persist when combined with conservative "
                "normalization and noise control."
            )
            direction = ExpectedDirection.HIGHER_SIGNAL_OUTPERFORMS
            field_classes = [FieldClass.PRICE, FieldClass.VOLUME]
            cadences = [UpdateCadence.DAILY]
            forbidden_patterns = ["missing_outer_rank", "unbounded_raw_momentum"]
        else:
            thesis_name = f"{agenda.family} exploratory signal"
            rationale = (
                f"Explore the {agenda.family} family under conservative expression constraints "
                "and explicit normalization."
            )
            direction = ExpectedDirection.HIGHER_SIGNAL_OUTPERFORMS
            field_classes = [FieldClass.PRICE, FieldClass.VOLUME]
            cadences = [UpdateCadence.DAILY]
            forbidden_patterns = ["missing_outer_rank"]

        return HypothesisSpec(
            hypothesis_id=f"hyp.{agenda.family}.{agenda.agenda_id.split('.')[-1]}",
            agenda_id=agenda.agenda_id,
            family=agenda.family,
            thesis_name=thesis_name,
            economic_rationale=rationale,
            expected_direction=direction,
            horizon=horizon,
            target_region=agenda.target_region,
            target_universe=agenda.target_universe,
            market_context=agenda.motivation,
            field_classes=field_classes,
            preferred_update_cadences=cadences,
            risk_notes=["Require final cross-sectional normalization"],
            evidence_requirements=["Positive risk-adjusted performance", "No severe critique issues"],
            forbidden_patterns=forbidden_patterns,
            confidence=min(max(agenda.priority, 0.2), 0.9),
            author="static_hypothesis_planner",
        )


class StaticBlueprintBuilder:
    def build(self, hypothesis: HypothesisSpec) -> SignalBlueprint:
        if hypothesis.family == ResearchFamily.QUALITY_DETERIORATION:
            return self._build_quality_deterioration_blueprint(hypothesis)
        if hypothesis.family == ResearchFamily.MOMENTUM:
            return self._build_momentum_blueprint(hypothesis)
        return self._build_generic_price_blueprint(hypothesis)

    def _build_quality_deterioration_blueprint(self, hypothesis: HypothesisSpec) -> SignalBlueprint:
        return SignalBlueprint(
            blueprint_id=f"bp.{hypothesis.hypothesis_id.split('.', 1)[1]}",
            hypothesis_id=hypothesis.hypothesis_id,
            summary="Medium-horizon quality deterioration with final cross-sectional ranking.",
            expression_intent="Compare weakening cash generation against leverage build-up.",
            field_selections=[
                FieldSelection(
                    field_id="cashflow_op",
                    field_class=FieldClass.FUNDAMENTAL,
                    update_cadence=UpdateCadence.QUARTERLY,
                    role=FieldRole.PRIMARY_SIGNAL,
                    rationale="Operating cashflow deterioration is the quality signal core.",
                ),
                FieldSelection(
                    field_id="debt_lt",
                    field_class=FieldClass.FUNDAMENTAL,
                    update_cadence=UpdateCadence.QUARTERLY,
                    role=FieldRole.DENOMINATOR_SCALE,
                    rationale="Long-term debt reflects leverage deterioration.",
                ),
                FieldSelection(
                    field_id="close",
                    field_class=FieldClass.PRICE,
                    update_cadence=UpdateCadence.DAILY,
                    role=FieldRole.CONFIRMATION,
                    rationale="Cross-sectional stability anchor for conservative synthesis.",
                ),
            ],
            primary_fields=["cashflow_op", "debt_lt"],
            secondary_fields=["close"],
            transform_plan=[
                TransformSpec(
                    name="cashflow_delta_63",
                    kind=TransformKind.DELTA,
                    input_fields=["cashflow_op"],
                    lookback_days=63,
                    rationale="Use a medium-horizon change signal for a slow fundamental field.",
                ),
                TransformSpec(
                    name="debt_delta_63",
                    kind=TransformKind.DELTA,
                    input_fields=["debt_lt"],
                    lookback_days=63,
                    rationale="Use a matching horizon for leverage change.",
                ),
                TransformSpec(
                    name="quality_spread",
                    kind=TransformKind.SPREAD,
                    input_fields=["cashflow_op", "debt_lt"],
                    rationale="Translate quality deterioration into a simple spread form.",
                ),
            ],
            normalization_plan=[
                NormalizationSpec(
                    kind=NormalizationKind.CROSS_SECTIONAL_RANK,
                    target=NormalizationTarget.FINAL_EXPRESSION,
                    rationale="Final rank reduces outlier domination and makes cross-sectional use safer.",
                )
            ],
            risk_control_plan=[
                RiskControlSpec(
                    kind=RiskControlKind.OUTER_RANK,
                    parameters={},
                    rationale="Explicit final ranking is mandatory for conservative first-pass signals.",
                ),
                RiskControlSpec(
                    kind=RiskControlKind.DENOMINATOR_FLOOR,
                    parameters={"epsilon": 0.01},
                    rationale="Avoid unstable division denominators.",
                ),
            ],
            operator_policy=OperatorPolicy(
                allowed_operators=["rank", "divide", "subtract", "add", "abs", "ts_delta"],
                forbidden_operators=["ts_sum", "group_backfill", "trade_when"],
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
                    rationale="Safe normalized spread around two key fields.",
                ),
                SkeletonTemplate(
                    template_id="skel.rank_inverse.001",
                    name="ranked_inverse_leverage",
                    template="rank(divide(FIELD_A, add(abs(FIELD_B), CONST_EPS)))",
                    slot_names=["FIELD_A", "FIELD_B", "CONST_EPS"],
                    rationale="Conservative ratio form with final ranking.",
                ),
            ],
            disallowed_patterns=["short_delay_on_slow_fundamentals", "missing_outer_rank"],
            target_expression_count=4,
            notes="Static blueprint for development-time workflow verification.",
        )

    def _build_momentum_blueprint(self, hypothesis: HypothesisSpec) -> SignalBlueprint:
        return SignalBlueprint(
            blueprint_id=f"bp.{hypothesis.hypothesis_id.split('.', 1)[1]}",
            hypothesis_id=hypothesis.hypothesis_id,
            summary="Intermediate momentum with volatility-aware normalization.",
            expression_intent="Capture medium-term continuation using safe time-series transforms.",
            field_selections=[
                FieldSelection(
                    field_id="close",
                    field_class=FieldClass.PRICE,
                    update_cadence=UpdateCadence.DAILY,
                    role=FieldRole.PRIMARY_SIGNAL,
                    rationale="Close carries the core continuation signal.",
                ),
                FieldSelection(
                    field_id="volume",
                    field_class=FieldClass.VOLUME,
                    update_cadence=UpdateCadence.DAILY,
                    role=FieldRole.CONFIRMATION,
                    rationale="Volume can confirm signal quality and tradability.",
                ),
            ],
            primary_fields=["close"],
            secondary_fields=["volume"],
            transform_plan=[
                TransformSpec(
                    name="close_delta_20",
                    kind=TransformKind.DELTA,
                    input_fields=["close"],
                    lookback_days=20,
                    rationale="Medium-term continuation proxy.",
                ),
                TransformSpec(
                    name="close_std_20",
                    kind=TransformKind.ROLLING_STDDEV,
                    input_fields=["close"],
                    lookback_days=20,
                    rationale="Volatility normalization.",
                ),
            ],
            normalization_plan=[
                NormalizationSpec(
                    kind=NormalizationKind.CROSS_SECTIONAL_RANK,
                    target=NormalizationTarget.FINAL_EXPRESSION,
                    rationale="Final ranking keeps the signal bounded and comparable.",
                )
            ],
            risk_control_plan=[
                RiskControlSpec(
                    kind=RiskControlKind.OUTER_RANK,
                    parameters={},
                    rationale="Require final ranking.",
                ),
            ],
            operator_policy=OperatorPolicy(
                allowed_operators=["rank", "divide", "add", "ts_delta", "ts_std_dev"],
                forbidden_operators=["trade_when", "group_backfill"],
                max_operator_count=5,
                max_nesting_depth=4,
                require_explicit_lookbacks=True,
                require_outer_normalization=True,
            ),
            skeleton_templates=[
                SkeletonTemplate(
                    template_id="skel.rank_delta_over_vol.001",
                    name="ranked_delta_over_vol",
                    template="rank(divide(ts_delta(FIELD_A, LOOKBACK_FAST), add(ts_std_dev(FIELD_A, LOOKBACK_SLOW), CONST_EPS)))",
                    slot_names=["FIELD_A", "LOOKBACK_FAST", "LOOKBACK_SLOW", "CONST_EPS"],
                    rationale="Classic continuation normalized by volatility.",
                )
            ],
            disallowed_patterns=["missing_outer_rank"],
            target_expression_count=3,
            notes="Static momentum blueprint.",
        )

    def _build_generic_price_blueprint(self, hypothesis: HypothesisSpec) -> SignalBlueprint:
        return self._build_momentum_blueprint(hypothesis)

