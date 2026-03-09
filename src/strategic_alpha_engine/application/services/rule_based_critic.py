from __future__ import annotations

import re

from strategic_alpha_engine.domain.critique_report import CritiqueIssue, CritiqueReport
from strategic_alpha_engine.domain.expression_candidate import ExpressionCandidate
from strategic_alpha_engine.domain.hypothesis_spec import HypothesisSpec
from strategic_alpha_engine.domain.signal_blueprint import SignalBlueprint

_SLOW_CADENCES = {"monthly", "quarterly", "irregular", "slow"}


class RuleBasedStrategicCritic:
    def critique(
        self,
        hypothesis: HypothesisSpec,
        blueprint: SignalBlueprint,
        candidate: ExpressionCandidate,
    ) -> CritiqueReport:
        issues: list[CritiqueIssue] = []
        repair_suggestions: list[str] = []

        if blueprint.operator_policy.require_outer_normalization and not candidate.outer_normalization_present:
            issues.append(
                CritiqueIssue(
                    code="missing_outer_rank",
                    severity="high",
                    message="Final expression lacks required outer normalization.",
                    suggestion="Wrap the final expression with rank(...) or an equivalent final normalization.",
                )
            )
            repair_suggestions.append("Add final cross-sectional rank to the expression.")

        forbidden_ops = set(blueprint.operator_policy.forbidden_operators)
        used_forbidden_ops = [op for op in candidate.operator_names if op in forbidden_ops]
        if used_forbidden_ops:
            issues.append(
                CritiqueIssue(
                    code="forbidden_operator_used",
                    severity="high",
                    message=f"Expression uses forbidden operators: {sorted(set(used_forbidden_ops))}",
                    suggestion="Regenerate the expression using only allowed operators.",
                )
            )
            repair_suggestions.append("Remove forbidden operators from the synthesis stage.")

        if candidate.operator_count > blueprint.operator_policy.max_operator_count:
            issues.append(
                CritiqueIssue(
                    code="operator_count_too_high",
                    severity="medium",
                    message=(
                        f"Expression uses {candidate.operator_count} operators, exceeding the limit of "
                        f"{blueprint.operator_policy.max_operator_count}."
                    ),
                    suggestion="Use a simpler skeleton with fewer nested operations.",
                )
            )

        if candidate.nesting_depth > blueprint.operator_policy.max_nesting_depth:
            issues.append(
                CritiqueIssue(
                    code="nesting_too_deep",
                    severity="medium",
                    message=(
                        f"Expression nesting depth {candidate.nesting_depth} exceeds the limit of "
                        f"{blueprint.operator_policy.max_nesting_depth}."
                    ),
                    suggestion="Flatten the expression structure.",
                )
            )

        missing_primary_fields = [field_id for field_id in blueprint.primary_fields if field_id not in candidate.expression]
        if missing_primary_fields:
            issues.append(
                CritiqueIssue(
                    code="missing_primary_field",
                    severity="high",
                    message=f"Expression omits primary blueprint fields: {missing_primary_fields}",
                    suggestion="Ensure all primary fields from the blueprint appear in the final formula.",
                )
            )

        slow_fields = {
            selection.field_id
            for selection in blueprint.field_selections
            if selection.update_cadence in _SLOW_CADENCES
        }
        for field_id in slow_fields:
            for operator_name in ("ts_delay", "ts_delta", "ts_mean", "ts_sum", "ts_rank", "ts_zscore"):
                pattern = re.compile(rf"{operator_name}\(\s*{field_id}\s*,\s*(\d+)\s*\)", re.IGNORECASE)
                match = pattern.search(candidate.expression)
                if match and int(match.group(1)) < 20:
                    issues.append(
                        CritiqueIssue(
                            code="short_temporal_lookback_on_slow_field",
                            severity="high",
                            message=(
                                f"Slow field '{field_id}' uses {operator_name} with short lookback "
                                f"{match.group(1)}."
                            ),
                            suggestion="Use longer lookbacks for slow-moving fields or remove the temporal transform.",
                        )
                    )
                    repair_suggestions.append("Increase temporal lookbacks on slow fields to at least 20 days.")
                    break

        tags = [hypothesis.family, "rule_based"]
        severity_penalty = {"high": 0.45, "medium": 0.2, "low": 0.08}
        overall_score = 1.0
        structural_score = 1.0
        economic_score = 1.0
        alignment_score = 1.0

        for issue in issues:
            penalty = severity_penalty[issue.severity]
            overall_score -= penalty
            if issue.code in {"missing_outer_rank", "operator_count_too_high", "nesting_too_deep"}:
                structural_score -= penalty
            elif issue.code in {"missing_primary_field"}:
                economic_score -= penalty
            else:
                alignment_score -= penalty

        overall_score = max(0.0, round(overall_score, 3))
        structural_score = max(0.0, round(structural_score, 3))
        economic_score = max(0.0, round(economic_score, 3))
        alignment_score = max(0.0, round(alignment_score, 3))
        passes = not any(issue.severity == "high" for issue in issues) and overall_score >= 0.6

        return CritiqueReport(
            critique_id=f"critique.{candidate.candidate_id}",
            candidate_id=candidate.candidate_id,
            blueprint_id=blueprint.blueprint_id,
            passes=passes,
            overall_score=overall_score,
            structural_quality_score=structural_score,
            economic_coherence_score=economic_score,
            data_horizon_alignment_score=alignment_score,
            issues=issues,
            repair_suggestions=repair_suggestions,
            tags=tags,
        )

