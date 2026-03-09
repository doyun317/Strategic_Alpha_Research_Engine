from __future__ import annotations

from typing import Any

from strategic_alpha_engine.domain.expression_candidate import ExpressionCandidate
from strategic_alpha_engine.domain.signal_blueprint import SignalBlueprint


class SkeletonCandidateSynthesizer:
    def synthesize(self, blueprint: SignalBlueprint) -> list[ExpressionCandidate]:
        candidates: list[ExpressionCandidate] = []
        field_pool = blueprint.primary_fields + [
            field_id for field_id in blueprint.secondary_fields if field_id not in blueprint.primary_fields
        ]
        if not field_pool:
            raise ValueError("blueprint must contain at least one field to synthesize candidates")

        epsilon = self._resolve_denominator_floor(blueprint)
        temporal_lookbacks = self._resolve_temporal_lookbacks(blueprint)

        for index in range(blueprint.target_expression_count):
            skeleton = blueprint.skeleton_templates[index % len(blueprint.skeleton_templates)]
            expression, bindings = self._fill_skeleton(
                skeleton.template,
                skeleton.slot_names,
                field_pool,
                epsilon,
                temporal_lookbacks,
            )
            candidates.append(
                ExpressionCandidate(
                    candidate_id=f"cand.{blueprint.blueprint_id}.{index + 1:03d}",
                    blueprint_id=blueprint.blueprint_id,
                    hypothesis_id=blueprint.hypothesis_id,
                    expression=expression,
                    generation_method="skeleton_fill",
                    skeleton_template_id=skeleton.template_id,
                    placeholder_bindings=bindings,
                )
            )
        return candidates

    @staticmethod
    def _resolve_denominator_floor(blueprint: SignalBlueprint) -> float:
        for risk_control in blueprint.risk_control_plan:
            if risk_control.kind == "denominator_floor":
                value = risk_control.parameters.get("epsilon")
                if isinstance(value, (int, float)):
                    return float(value)
        return 0.01

    @staticmethod
    def _resolve_temporal_lookbacks(blueprint: SignalBlueprint) -> list[int]:
        values = [transform.lookback_days for transform in blueprint.transform_plan if transform.lookback_days]
        if not values:
            return [5, 20]
        unique = []
        for value in values:
            if value not in unique:
                unique.append(value)
        return unique

    def _fill_skeleton(
        self,
        template: str,
        slot_names: list[str],
        field_pool: list[str],
        epsilon: float,
        temporal_lookbacks: list[int],
    ) -> tuple[str, dict[str, Any]]:
        expression = template
        bindings: dict[str, Any] = {}
        field_index = 0
        lookback_index = 0

        for slot_name in slot_names:
            if slot_name.startswith("FIELD_"):
                value = field_pool[field_index % len(field_pool)]
                field_index += 1
            elif slot_name.startswith("LOOKBACK_"):
                value = temporal_lookbacks[lookback_index % len(temporal_lookbacks)]
                lookback_index += 1
            elif slot_name.startswith("CONST_"):
                value = epsilon
            else:
                raise ValueError(f"Unsupported skeleton slot: {slot_name}")
            bindings[slot_name] = value
            expression = expression.replace(slot_name, str(value))

        return expression, bindings

