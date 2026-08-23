"""Shared deterministic helpers for the D16 deployment-governance depth set."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty


_FORBIDDEN_OUTPUT_MARKERS = ("password", "token", "api_key", "signing_secret")


def deployment_address(value: Any) -> str:
    return content_hash(jsonable(value))


def require_mapping(value: Any, label: str = "value") -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{label} must be an object")
    return value


def require_sequence(value: Any, label: str = "value") -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValidationError(f"{label} must be an array")
    return tuple(value)


def stable_texts(values: Iterable[Any]) -> tuple[str, ...]:
    return tuple(sorted({str(item).strip() for item in values if str(item).strip()}))


def normalized_issue_codes(values: Iterable[Any]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(item).split(":", 1)[0] for item in values if str(item)))


def contains_forbidden_output(value: Any) -> bool:
    serialized = str(jsonable(value)).lower()
    return any(marker in serialized for marker in _FORBIDDEN_OUTPUT_MARKERS)


def safe_projection(value: Mapping[str, Any], allowed: Iterable[str]) -> dict[str, Any]:
    keys = set(allowed)
    return {str(key): jsonable(item) for key, item in value.items() if str(key) in keys}


def count_states(values: Iterable[Any]) -> dict[str, int]:
    return dict(sorted(Counter(str(getattr(item, "state", item)) for item in values).items()))


def bounded_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round(min(1.0, max(0.0, numerator / denominator)), 6)


def addressed_body(body: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(body)
    result["content_address"] = deployment_address(body)
    return result


def require_address(value: Any, label: str = "content_address") -> str:
    address = require_non_empty(str(value), label)
    if not address.startswith("sha256:"):
        raise ValidationError(f"{label} must use SHA-256")
    return address


__all__ = [
    "addressed_body",
    "bounded_ratio",
    "contains_forbidden_output",
    "count_states",
    "deployment_address",
    "normalized_issue_codes",
    "require_address",
    "require_mapping",
    "require_sequence",
    "safe_projection",
    "stable_texts",
]
