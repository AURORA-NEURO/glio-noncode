"""Canonical normalization and safe projection for D07 mappings."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .errors import ValidationError

_HIDDEN_KEYS = frozenset(
    {"payload", "operation_payload", "family_record", "input_text", "track_text"}
)


def normalize_chromatin_architecture_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    """Sort object keys and normalize scalar containers without changing values."""

    if not isinstance(value, Mapping):
        raise ValidationError("D07 normalization requires an object mapping")
    return {
        str(key): _normalize(item)
        for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
    }


def _normalize(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _normalize(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_normalize(item) for item in value]
    if isinstance(value, float):
        return round(value, 12)
    return value


def strip_chromatin_architecture_payloads(value: Any) -> Any:
    """Remove raw record payloads while retaining structural receipt fields."""

    if isinstance(value, Mapping):
        return {
            str(key): strip_chromatin_architecture_payloads(item)
            for key, item in value.items()
            if str(key) not in _HIDDEN_KEYS
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [strip_chromatin_architecture_payloads(item) for item in value]
    return value


def chromatin_architecture_public_projection(value: Mapping[str, Any]) -> dict[str, Any]:
    return dict(
        strip_chromatin_architecture_payloads(normalize_chromatin_architecture_mapping(value))
    )


__all__ = [
    "chromatin_architecture_public_projection",
    "normalize_chromatin_architecture_mapping",
    "strip_chromatin_architecture_payloads",
]
