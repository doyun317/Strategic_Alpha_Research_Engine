from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from strategic_alpha_engine.domain.base import EngineModel
from strategic_alpha_engine.domain.common import (
    FIELD_IDENTIFIER_PATTERN,
    IDENTIFIER_PATTERN,
    SLOT_NAME_PATTERN,
    ensure_unique_lower_text,
    ensure_unique_sequence,
)
from strategic_alpha_engine.domain.enums import (
    FieldClass,
    FieldRole,
    NormalizationKind,
    NormalizationTarget,
    RiskControlKind,
    TransformKind,
    UpdateCadence,
)

_LOOKBACK_REQUIRED_KINDS = {
    TransformKind.DELTA,
    TransformKind.DELAY,
    TransformKind.TS_RANK,
    TransformKind.TS_ZSCORE,
    TransformKind.VOLATILITY_SCALE,
    TransformKind.SMOOTHING,
    TransformKind.DECAY_LINEAR,
    TransformKind.ROLLING_MEAN,
    TransformKind.ROLLING_SUM,
    TransformKind.ROLLING_STDDEV,
}
_LOOKBACK_FORBIDDEN_KINDS = {
    TransformKind.RATIO,
    TransformKind.SPREAD,
    TransformKind.RANK,
    TransformKind.ZSCORE,
    TransformKind.LOG,
}
_TEMPORAL_KINDS = _LOOKBACK_REQUIRED_KINDS
_SLOW_CADENCES = {
    UpdateCadence.MONTHLY,
    UpdateCadence.QUARTERLY,
    UpdateCadence.IRREGULAR,
    UpdateCadence.SLOW,
}
_FINAL_NORMALIZATION_KINDS = {
    NormalizationKind.CROSS_SECTIONAL_RANK,
    NormalizationKind.CROSS_SECTIONAL_ZSCORE,
}


class FieldSelection(EngineModel):
    field_id: str = Field(pattern=FIELD_IDENTIFIER_PATTERN)
    field_class: FieldClass
    update_cadence: UpdateCadence
    role: FieldRole
    rationale: str = Field(min_length=8, max_length=240)


class TransformSpec(EngineModel):
    name: str = Field(min_length=3, max_length=80)
    kind: TransformKind
    input_fields: list[str] = Field(min_length=1, max_length=3)
    lookback_days: int | None = Field(default=None, ge=1, le=2520)
    constant: float | None = None
    rationale: str | None = Field(default=None, max_length=240)

    @field_validator("input_fields")
    @classmethod
    def validate_input_fields(cls, value: list[str]) -> list[str]:
        return ensure_unique_sequence(value, "input_fields")

    @model_validator(mode="after")
    def validate_lookback_rules(self) -> "TransformSpec":
        if self.kind in _LOOKBACK_REQUIRED_KINDS and self.lookback_days is None:
            raise ValueError(f"{self.kind} requires lookback_days")
        if self.kind in _LOOKBACK_FORBIDDEN_KINDS and self.lookback_days is not None:
            raise ValueError(f"{self.kind} must not declare lookback_days")
        return self


class NormalizationSpec(EngineModel):
    kind: NormalizationKind
    target: NormalizationTarget = NormalizationTarget.FINAL_EXPRESSION
    rationale: str = Field(min_length=8, max_length=200)


class RiskControlSpec(EngineModel):
    kind: RiskControlKind
    parameters: dict[str, int | float | str | bool] = Field(default_factory=dict)
    rationale: str = Field(min_length=8, max_length=200)


class OperatorPolicy(EngineModel):
    allowed_operators: list[str] = Field(default_factory=list, max_length=64)
    forbidden_operators: list[str] = Field(default_factory=list, max_length=64)
    max_operator_count: int = Field(default=6, ge=1, le=20)
    max_nesting_depth: int = Field(default=4, ge=1, le=10)
    require_explicit_lookbacks: bool = True
    require_outer_normalization: bool = True

    @field_validator("allowed_operators", "forbidden_operators")
    @classmethod
    def normalize_operator_lists(cls, value: list[str], info) -> list[str]:
        return ensure_unique_lower_text(value, info.field_name)

    @model_validator(mode="after")
    def validate_operator_overlap(self) -> "OperatorPolicy":
        overlap = set(self.allowed_operators) & set(self.forbidden_operators)
        if overlap:
            raise ValueError(f"operator policy overlaps between allow/forbid: {sorted(overlap)}")
        return self


class SkeletonTemplate(EngineModel):
    template_id: str = Field(pattern=IDENTIFIER_PATTERN)
    name: str = Field(min_length=3, max_length=80)
    template: str = Field(min_length=8, max_length=280)
    slot_names: list[str] = Field(min_length=1, max_length=8)
    rationale: str = Field(min_length=8, max_length=200)

    @field_validator("slot_names")
    @classmethod
    def validate_slot_names(cls, value: list[str]) -> list[str]:
        validated = ensure_unique_sequence(value, "slot_names")
        for slot_name in validated:
            if not __import__("re").match(SLOT_NAME_PATTERN, slot_name):
                raise ValueError("slot_names must be uppercase placeholders like FIELD_A")
        return validated

    @model_validator(mode="after")
    def validate_slot_usage(self) -> "SkeletonTemplate":
        missing = [slot_name for slot_name in self.slot_names if slot_name not in self.template]
        if missing:
            raise ValueError(f"slot_names missing from template: {missing}")
        return self


class SignalBlueprint(EngineModel):
    blueprint_id: str = Field(pattern=IDENTIFIER_PATTERN)
    hypothesis_id: str = Field(pattern=IDENTIFIER_PATTERN)
    summary: str = Field(min_length=12, max_length=240)
    expression_intent: str = Field(min_length=12, max_length=240)
    field_selections: list[FieldSelection] = Field(min_length=1, max_length=10)
    primary_fields: list[str] = Field(min_length=1, max_length=4)
    secondary_fields: list[str] = Field(default_factory=list, max_length=6)
    transform_plan: list[TransformSpec] = Field(min_length=1, max_length=10)
    normalization_plan: list[NormalizationSpec] = Field(min_length=1, max_length=6)
    risk_control_plan: list[RiskControlSpec] = Field(default_factory=list, max_length=8)
    operator_policy: OperatorPolicy = Field(default_factory=OperatorPolicy)
    skeleton_templates: list[SkeletonTemplate] = Field(min_length=1, max_length=8)
    disallowed_patterns: list[str] = Field(default_factory=list, max_length=12)
    target_expression_count: int = Field(default=5, ge=1, le=20)
    notes: str | None = Field(default=None, max_length=300)

    @field_validator("primary_fields", "secondary_fields")
    @classmethod
    def validate_field_lists(cls, value: list[str], info) -> list[str]:
        return ensure_unique_sequence(value, info.field_name)

    @field_validator("disallowed_patterns")
    @classmethod
    def validate_disallowed_patterns(cls, value: list[str]) -> list[str]:
        return ensure_unique_lower_text(value, "disallowed_patterns")

    @model_validator(mode="after")
    def validate_blueprint(self) -> "SignalBlueprint":
        selected_fields = {selection.field_id: selection for selection in self.field_selections}
        if len(selected_fields) != len(self.field_selections):
            raise ValueError("field_selections must not contain duplicate field_id values")

        unknown_primary = set(self.primary_fields) - set(selected_fields)
        if unknown_primary:
            raise ValueError(f"primary_fields missing from field_selections: {sorted(unknown_primary)}")

        unknown_secondary = set(self.secondary_fields) - set(selected_fields)
        if unknown_secondary:
            raise ValueError(f"secondary_fields missing from field_selections: {sorted(unknown_secondary)}")

        overlap = set(self.primary_fields) & set(self.secondary_fields)
        if overlap:
            raise ValueError(f"primary_fields and secondary_fields overlap: {sorted(overlap)}")

        for transform in self.transform_plan:
            missing_fields = set(transform.input_fields) - set(selected_fields)
            if missing_fields:
                raise ValueError(
                    f"transform '{transform.name}' references unknown fields: {sorted(missing_fields)}"
                )
            if transform.lookback_days is None:
                continue
            if transform.kind not in _TEMPORAL_KINDS:
                continue
            for field_id in transform.input_fields:
                cadence = selected_fields[field_id].update_cadence
                if cadence in _SLOW_CADENCES and transform.lookback_days < 20:
                    raise ValueError(
                        "slow-moving fields must not use short temporal lookbacks "
                        f"(field={field_id}, kind={transform.kind}, lookback={transform.lookback_days})"
                    )

        if self.operator_policy.require_outer_normalization:
            has_final_normalization = any(
                normalization.target == NormalizationTarget.FINAL_EXPRESSION
                and normalization.kind in _FINAL_NORMALIZATION_KINDS
                for normalization in self.normalization_plan
            )
            if not has_final_normalization:
                raise ValueError(
                    "operator_policy.require_outer_normalization=True requires a final-expression "
                    "cross-sectional normalization"
                )

        return self

