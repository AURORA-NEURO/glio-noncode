"""Defensive parsing, issue normalization, and safe output helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .serialization import content_hash, jsonable

FORBIDDEN_MARKERS = ("api_key", "access_token", "authorization", "password", "patient_id", "sample_id", "secret", "token")


def required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty text")
    return value.strip()


def bounded(value: Any, field: str, *, lower: float = 0.0, upper: float = 1.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if number < lower or number > upper:
        raise ValueError(f"{field} must be between {lower} and {upper}")
    return number


def positive_number(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if number <= 0:
        raise ValueError(f"{field} must be positive")
    return number


def mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return value


def sequence(value: Any, field: str) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"{field} must be a list")
    return tuple(value)


def context_matches(value: Any, expected: str) -> bool:
    return isinstance(value, str) and value.strip() == expected


def address(value: Any) -> str:
    return content_hash(jsonable(value))


def normalized_issue_codes(codes: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted({str(code).strip() for code in codes if str(code).strip()}))


def contains_forbidden_marker(value: Any) -> bool:
    text = str(jsonable(value)).lower()
    return any(marker in text for marker in FORBIDDEN_MARKERS)


def safe_output(value: Mapping[str, Any]) -> dict[str, Any]:
    """Return a JSON-safe projection without credential-like fields.

    The operation layer never echoes signing material or private request fields.  A
    field is removed recursively by name, while content addresses and public IDs are
    retained for audit joins.
    """
    def clean(item: Any, key: str = "") -> Any:
        lowered = key.lower()
        if any(marker in lowered for marker in FORBIDDEN_MARKERS):
            return "[redacted]"
        if isinstance(item, Mapping):
            return {str(k): clean(v, str(k)) for k, v in item.items() if not any(marker in str(k).lower() for marker in FORBIDDEN_MARKERS)}
        if isinstance(item, (list, tuple)):
            return [clean(v, key) for v in item]
        return item
    return clean(value)


def output_address(value: Mapping[str, Any]) -> str:
    return address(safe_output(value))


def duplicate_values(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted({value for value in values if values.count(value) > 1}))


def sorted_unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values}))


__all__ = [
    "FORBIDDEN_MARKERS",
    "address",
    "bounded",
    "contains_forbidden_marker",
    "context_matches",
    "duplicate_values",
    "mapping",
    "normalized_issue_codes",
    "output_address",
    "positive_number",
    "required_text",
    "safe_output",
    "sequence",
    "sorted_unique",
]
