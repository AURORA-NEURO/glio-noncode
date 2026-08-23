"""Shared deterministic helpers for validation-release modules."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty


def text(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be text")
    return value.strip()


def required_text(value: Any, field: str) -> str:
    return require_non_empty(text(value, field), field)


def mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return value


def sequence(value: Any, field: str) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"{field} must be an array")
    return tuple(value)


def bounded(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"{field} must be between zero and one")
    return number


def positive_number(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if number <= 0:
        raise ValueError(f"{field} must be positive")
    return number


def address(value: Any) -> str:
    return content_hash(jsonable(value))


def normalized_issue_codes(codes: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted({str(code).strip() for code in codes if str(code).strip()}))


def safe_output(value: Any) -> dict[str, Any]:
    payload = jsonable(value)
    if not isinstance(payload, dict):
        return {"value": payload}
    return payload


def contains_forbidden_marker(value: Any) -> bool:
    serialized = str(jsonable(value)).lower()
    return any(marker in serialized for marker in ("password", "api_key", "signing_secret", "access_token"))


def context_matches(value: Any, expected: str) -> bool:
    return isinstance(value, str) and value == expected


__all__ = [
    "address",
    "bounded",
    "contains_forbidden_marker",
    "context_matches",
    "mapping",
    "normalized_issue_codes",
    "positive_number",
    "required_text",
    "safe_output",
    "sequence",
    "text",
]
