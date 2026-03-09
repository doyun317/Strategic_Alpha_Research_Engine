from __future__ import annotations

import re

from strategic_alpha_engine.domain.expression_candidate import ExpressionCandidate
from strategic_alpha_engine.domain.metadata_catalog import MetadataCatalog
from strategic_alpha_engine.domain.signal_blueprint import SignalBlueprint
from strategic_alpha_engine.domain.static_validation import StaticValidationIssue, StaticValidationReport

_NUMERIC_LITERAL_PATTERN = re.compile(r"^[+-]?(?:\d+(?:\.\d+)?|\.\d+)$")


class MetadataBackedStaticValidator:
    def __init__(self, catalog: MetadataCatalog):
        self.catalog = catalog

    def validate(
        self,
        blueprint: SignalBlueprint,
        candidate: ExpressionCandidate,
    ) -> StaticValidationReport:
        issues: list[StaticValidationIssue] = []
        allowed_fields = {selection.field_id for selection in blueprint.field_selections}
        allowed_operators = set(blueprint.operator_policy.allowed_operators)
        forbidden_operators = set(blueprint.operator_policy.forbidden_operators)

        if not _has_balanced_parentheses(candidate.expression):
            issues.append(
                StaticValidationIssue(
                    code="unbalanced_parentheses",
                    severity="high",
                    message="Expression parentheses are not balanced.",
                    suggestion="Rebuild the expression from a valid skeleton template.",
                )
            )

        unknown_fields = [field_id for field_id in candidate.referenced_fields if field_id not in allowed_fields]
        if unknown_fields:
            issues.append(
                StaticValidationIssue(
                    code="unknown_field",
                    severity="high",
                    message=f"Expression references fields outside the blueprint: {sorted(unknown_fields)}",
                    suggestion="Restrict the expression to blueprint-selected fields only.",
                )
            )

        missing_metadata_fields = [
            field_id
            for field_id in candidate.referenced_fields
            if field_id in allowed_fields and self.catalog.get_field(field_id) is None
        ]
        if missing_metadata_fields:
            issues.append(
                StaticValidationIssue(
                    code="missing_field_metadata",
                    severity="high",
                    message=f"Field metadata is missing for: {sorted(missing_metadata_fields)}",
                    suggestion="Add the referenced fields to the metadata catalog before synthesis.",
                )
            )

        parsed_calls = _extract_function_calls(candidate.expression)
        for operator_name, argument_texts in parsed_calls:
            metadata = self.catalog.get_operator(operator_name)
            if metadata is None:
                issues.append(
                    StaticValidationIssue(
                        code="unknown_operator",
                        severity="high",
                        message=f"Operator '{operator_name}' is missing from the metadata catalog.",
                        suggestion="Add the operator to the catalog or remove it from synthesis.",
                    )
                )
                continue

            if allowed_operators and operator_name not in allowed_operators:
                issues.append(
                    StaticValidationIssue(
                        code="operator_not_allowed",
                        severity="high",
                        message=f"Operator '{operator_name}' is outside the blueprint allow-list.",
                        suggestion="Use only operators declared in operator_policy.allowed_operators.",
                    )
                )

            if operator_name in forbidden_operators:
                issues.append(
                    StaticValidationIssue(
                        code="forbidden_operator",
                        severity="high",
                        message=f"Operator '{operator_name}' is explicitly forbidden by the blueprint.",
                        suggestion="Replace the forbidden operator with an allowed alternative.",
                    )
                )

            argument_count = len(argument_texts)
            if not metadata.min_arity <= argument_count <= metadata.max_arity:
                issues.append(
                    StaticValidationIssue(
                        code="invalid_operator_arity",
                        severity="high",
                        message=(
                            f"Operator '{operator_name}' received {argument_count} arguments but expects "
                            f"{metadata.min_arity}..{metadata.max_arity}."
                        ),
                        suggestion="Regenerate the expression using the operator's valid arity range.",
                    )
                )

            has_numeric_literal = any(_NUMERIC_LITERAL_PATTERN.match(argument) for argument in argument_texts)
            if has_numeric_literal and not metadata.supports_constants:
                issues.append(
                    StaticValidationIssue(
                        code="constant_argument_not_allowed",
                        severity="high",
                        message=f"Operator '{operator_name}' does not allow numeric literal arguments.",
                        suggestion="Remove literal constants or use an operator that explicitly supports them.",
                    )
                )

        passes = not any(issue.severity == "high" for issue in issues)
        return StaticValidationReport(
            validation_id=f"static.validation.{candidate.candidate_id}",
            candidate_id=candidate.candidate_id,
            blueprint_id=candidate.blueprint_id,
            passes=passes,
            checked_operator_count=len(parsed_calls),
            checked_field_count=len(candidate.referenced_fields),
            issues=issues,
        )


def _has_balanced_parentheses(expression: str) -> bool:
    depth = 0
    for char in expression:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def _extract_function_calls(expression: str) -> list[tuple[str, list[str]]]:
    calls: list[tuple[str, list[str]]] = []
    index = 0
    while index < len(expression):
        if expression[index].isalpha() or expression[index] == "_":
            start = index
            while index < len(expression) and (expression[index].isalnum() or expression[index] == "_"):
                index += 1
            operator_name = expression[start:index].lower()

            probe = index
            while probe < len(expression) and expression[probe].isspace():
                probe += 1

            if probe < len(expression) and expression[probe] == "(":
                closing_index = _find_matching_paren(expression, probe)
                if closing_index == -1:
                    break
                arguments_segment = expression[probe + 1 : closing_index]
                argument_texts = _split_top_level_arguments(arguments_segment)
                calls.append((operator_name, argument_texts))
                for argument_text in argument_texts:
                    calls.extend(_extract_function_calls(argument_text))
                index = closing_index + 1
                continue
        index += 1
    return calls


def _find_matching_paren(expression: str, open_index: int) -> int:
    depth = 0
    for index in range(open_index, len(expression)):
        if expression[index] == "(":
            depth += 1
        elif expression[index] == ")":
            depth -= 1
            if depth == 0:
                return index
    return -1


def _split_top_level_arguments(segment: str) -> list[str]:
    stripped_segment = segment.strip()
    if not stripped_segment:
        return []

    arguments: list[str] = []
    current: list[str] = []
    depth = 0

    for char in segment:
        if char == "," and depth == 0:
            arguments.append("".join(current).strip())
            current = []
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        current.append(char)

    if current:
        arguments.append("".join(current).strip())
    return arguments
