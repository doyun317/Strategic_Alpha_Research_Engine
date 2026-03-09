from __future__ import annotations

import re

from pydantic import Field, computed_field, field_validator, model_validator

from strategic_alpha_engine.domain.base import EngineModel
from strategic_alpha_engine.domain.common import IDENTIFIER_PATTERN

_OPERATOR_PATTERN = re.compile(r"\b([a-z_][a-z0-9_]*)\s*\(", flags=re.IGNORECASE)
_FIELD_PATTERN = re.compile(r"\b([A-Za-z][A-Za-z0-9_]*)\b")
_RESERVED_TOKENS = {
    "rank",
    "ts_rank",
    "ts_zscore",
    "ts_delta",
    "ts_delay",
    "ts_mean",
    "ts_std_dev",
    "ts_sum",
    "add",
    "subtract",
    "multiply",
    "divide",
    "abs",
    "log",
    "max",
    "min",
    "reverse",
    "signed_power",
    "sqrt",
}


def _normalize_expression(expression: str) -> str:
    return re.sub(r"\s+", "", expression).lower()


def _count_nesting_depth(expression: str) -> int:
    depth = 0
    max_depth = 0
    for ch in expression:
        if ch == "(":
            depth += 1
            max_depth = max(max_depth, depth)
        elif ch == ")":
            depth = max(depth - 1, 0)
    return max_depth


def _extract_operator_names(expression: str) -> list[str]:
    return [match.group(1).lower() for match in _OPERATOR_PATTERN.finditer(expression)]


def _extract_field_tokens(expression: str) -> list[str]:
    operators = set(_extract_operator_names(expression))
    fields: list[str] = []
    seen: set[str] = set()
    for match in _FIELD_PATTERN.finditer(expression):
        token = match.group(1)
        lowered = token.lower()
        if lowered in operators or lowered in _RESERVED_TOKENS:
            continue
        if token.isdigit():
            continue
        if lowered in {"true", "false", "nan"}:
            continue
        if lowered in seen:
            continue
        seen.add(lowered)
        fields.append(token)
    return fields


class ExpressionCandidate(EngineModel):
    candidate_id: str = Field(pattern=IDENTIFIER_PATTERN)
    blueprint_id: str = Field(pattern=IDENTIFIER_PATTERN)
    hypothesis_id: str = Field(pattern=IDENTIFIER_PATTERN)
    expression: str = Field(min_length=4, max_length=500)
    generation_method: str = Field(
        default="skeleton_fill",
        pattern=r"^(skeleton_fill|llm_synthesis|manual)$",
    )
    skeleton_template_id: str | None = Field(default=None, pattern=IDENTIFIER_PATTERN)
    placeholder_bindings: dict[str, str | int | float] = Field(default_factory=dict)
    notes: str | None = Field(default=None, max_length=240)

    @field_validator("expression")
    @classmethod
    def validate_expression(cls, value: str) -> str:
        if value.count("(") != value.count(")"):
            raise ValueError("expression must contain balanced parentheses")
        return " ".join(value.split())

    @model_validator(mode="after")
    def validate_skeleton_metadata(self) -> "ExpressionCandidate":
        if self.generation_method == "skeleton_fill" and not self.skeleton_template_id:
            raise ValueError("skeleton_fill candidates must include skeleton_template_id")
        return self

    @computed_field
    @property
    def normalized_expression(self) -> str:
        return _normalize_expression(self.expression)

    @computed_field
    @property
    def operator_names(self) -> list[str]:
        return _extract_operator_names(self.expression)

    @computed_field
    @property
    def operator_count(self) -> int:
        return len(self.operator_names)

    @computed_field
    @property
    def nesting_depth(self) -> int:
        return _count_nesting_depth(self.expression)

    @computed_field
    @property
    def outer_normalization_present(self) -> bool:
        normalized = self.normalized_expression
        return normalized.startswith("rank(") or normalized.startswith("zscore(")

    @computed_field
    @property
    def referenced_fields(self) -> list[str]:
        return _extract_field_tokens(self.expression)

    @computed_field
    @property
    def complexity_score(self) -> float:
        return round(
            self.operator_count + (self.nesting_depth * 0.5) + (len(self.referenced_fields) * 0.25),
            3,
        )

