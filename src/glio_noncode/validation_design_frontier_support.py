"""Defensive parsing for validation planning payloads."""
from __future__ import annotations
from collections.abc import Mapping, Sequence
from typing import Any
from .serialization import content_hash, jsonable

PRIVATE_MARKERS = ("api_key", "access_token", "authorization", "password", "patient_id", "sample_id", "token")

def required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip(): raise ValueError(f"{field} must be non-empty text")
    return value.strip()

def mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping): raise ValueError(f"{field} must be an object")
    return value

def sequence(value: Any, field: str) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence): raise ValueError(f"{field} must be a list")
    return tuple(value)

def positive_integer(value: Any, field: str) -> int:
    try: number = int(value)
    except (TypeError, ValueError) as exc: raise ValueError(f"{field} must be an integer") from exc
    if number <= 0: raise ValueError(f"{field} must be positive")
    return number

def context_matches(value: Any, expected: str) -> bool:
    return isinstance(value, str) and value.strip() == expected

def normalized_issue_codes(codes: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted({str(code).strip() for code in codes if str(code).strip()}))

def address(value: Any) -> str:
    return content_hash(jsonable(value))

def contains_private_marker(value: Any) -> bool:
    text = str(jsonable(value)).lower()
    return any(marker in text for marker in PRIVATE_MARKERS)

def safe_output(value: Mapping[str, Any]) -> dict[str, Any]:
    def clean(item: Any, key: str = "") -> Any:
        if any(marker in key.lower() for marker in PRIVATE_MARKERS): return "[redacted]"
        if isinstance(item, Mapping): return {str(k): clean(v, str(k)) for k, v in item.items() if not any(marker in str(k).lower() for marker in PRIVATE_MARKERS)}
        if isinstance(item, (list, tuple)): return [clean(value, key) for value in item]
        return item
    return clean(value)

__all__ = ["PRIVATE_MARKERS", "address", "contains_private_marker", "context_matches", "mapping", "normalized_issue_codes", "positive_integer", "required_text", "safe_output", "sequence"]
