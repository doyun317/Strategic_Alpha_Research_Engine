from __future__ import annotations

from typing import TypeVar


IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$"
FIELD_IDENTIFIER_PATTERN = r"^[A-Za-z][A-Za-z0-9_]{1,63}$"
SLOT_NAME_PATTERN = r"^[A-Z][A-Z0-9_]{1,31}$"

T = TypeVar("T")


def ensure_unique_sequence(values: list[T], field_name: str) -> list[T]:
    seen: set[T] = set()
    result: list[T] = []
    for value in values:
        normalized = value.strip() if isinstance(value, str) else value
        if isinstance(normalized, str) and not normalized:
            raise ValueError(f"{field_name} must not contain empty strings")
        if normalized in seen:
            raise ValueError(f"{field_name} must not contain duplicates")
        seen.add(normalized)
        result.append(normalized)
    return result


def ensure_unique_lower_text(values: list[str], field_name: str) -> list[str]:
    lowered = [value.strip().lower() for value in values]
    return ensure_unique_sequence(lowered, field_name)

