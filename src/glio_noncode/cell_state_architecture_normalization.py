"""Stable row normalization and field-level redaction for D08 outputs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .serialization import content_hash, jsonable

D08_HIDDEN_FIELDS = frozenset({"payload", "input_text", "track_text", "raw_text", "records_text"})
D08_SORT_KEYS = ("fixture_id", "operation_id", "case_id", "source_id", "content_address")


def normalize_d08_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): normalize_d08_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [normalize_d08_value(item) for item in value]
    return jsonable(value)


def review_safe_projection(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): review_safe_projection(item)
            for key, item in value.items()
            if str(key) not in D08_HIDDEN_FIELDS
        }
    if isinstance(value, (list, tuple)):
        return [review_safe_projection(item) for item in value]
    return jsonable(value)


def normalized_address(value: Any) -> str:
    return content_hash(normalize_d08_value(value))


def normalize_case_rows(rows: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    return tuple(review_safe_projection(normalize_d08_value(row)) for row in rows)


__all__ = [
    "D08_HIDDEN_FIELDS",
    "D08_SORT_KEYS",
    "normalize_case_rows",
    "normalize_d08_value",
    "normalized_address",
    "review_safe_projection",
]
