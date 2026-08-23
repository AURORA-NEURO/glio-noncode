"""Defensive parsing and bounded projection helpers for planning operations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .serialization import content_hash


PRIVATE_MARKERS = (
    "api_key",
    "access_token",
    "password",
    "patient_id",
    "sample_id",
    "subject_id",
    "email",
    "phone",
)


def address(value: Any, *, prefix: str = "planning") -> str:
    """Return a stable address for a public planning artifact."""

    return content_hash(value, prefix=prefix)


def mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def sequence(value: Any, name: str) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"{name} must be a sequence")
    return tuple(value)


def required_text(value: Any, name: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise ValueError(f"{name} is required")
    return result


def optional_text(value: Any) -> str | None:
    result = str(value or "").strip()
    return result or None


def non_negative_integer(value: Any, name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    result = int(value)
    if result < 0:
        raise ValueError(f"{name} must be non-negative")
    return result


def positive_integer(value: Any, name: str) -> int:
    result = non_negative_integer(value, name)
    if result < 1:
        raise ValueError(f"{name} must be positive")
    return result


def finite_number(value: Any, name: str) -> float:
    result = float(value)
    if result != result or result in (float("inf"), float("-inf")):
        raise ValueError(f"{name} must be finite")
    return result


def bounded_fraction(value: Any, name: str) -> float:
    result = finite_number(value, name)
    if not 0.0 < result < 1.0:
        raise ValueError(f"{name} must be between zero and one")
    return result


def context_matches(value: Any, required: str) -> bool:
    return str(value or "").strip() == required


def dna(value: Any, name: str, *, allow_n: bool = True) -> str:
    result = required_text(value, name).upper().replace(" ", "")
    alphabet = "ACGTN" if allow_n else "ACGT"
    if any(base not in alphabet for base in result):
        raise ValueError(f"{name} contains unsupported bases")
    return result


def unique_text(values: Sequence[Any], name: str) -> tuple[str, ...]:
    result = tuple(required_text(value, name) for value in values)
    return tuple(dict.fromkeys(result))


def issue_codes(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if str(value).strip()))


def safe_output(value: Any) -> Any:
    """Project arbitrary input without carrying private-looking fields forward."""

    if isinstance(value, Mapping):
        return {
            str(key): "[omitted]" if str(key).lower() in PRIVATE_MARKERS else safe_output(item)
            for key, item in value.items()
            if str(key).lower() not in {"raw_record", "raw_text"}
        }
    if isinstance(value, (tuple, list)):
        return tuple(safe_output(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted(safe_output(item) for item in value))
    return value


def contains_private_marker(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            str(key).lower() in PRIVATE_MARKERS or contains_private_marker(item)
            for key, item in value.items()
        )
    if isinstance(value, (tuple, list, set)):
        return any(contains_private_marker(item) for item in value)
    return False


def state_for(issues: Sequence[str], *, has_output: bool, blocked_codes: Sequence[str] = ()) -> str:
    codes = set(issues)
    if codes.intersection(blocked_codes):
        return "blocked"
    if not has_output and "empty_source" in codes:
        return "abstained"
    if issues:
        return "review"
    return "ready_for_review"


__all__ = [
    "PRIVATE_MARKERS",
    "address",
    "bounded_fraction",
    "contains_private_marker",
    "context_matches",
    "dna",
    "finite_number",
    "issue_codes",
    "mapping",
    "non_negative_integer",
    "optional_text",
    "positive_integer",
    "required_text",
    "safe_output",
    "sequence",
    "state_for",
    "unique_text",
]
