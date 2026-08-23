"""Stable payload-free D06 projections."""

from __future__ import annotations

from typing import Any

from .serialization import jsonable


def normalize_sequence_architecture_mapping(value: Any) -> dict[str, Any]:
    normalized = jsonable(value)
    if not isinstance(normalized, dict):
        raise TypeError("D06 projection must be a mapping")
    return dict(sorted(normalized.items(), key=lambda item: item[0]))


def strip_sequence_architecture_payloads(value: Any) -> dict[str, Any]:
    def strip(item: Any) -> Any:
        if isinstance(item, dict):
            return {
                key: strip(value)
                for key, value in item.items()
                if key not in {"payload", "family_payload", "input_text"}
            }
        if isinstance(item, list):
            return [strip(value) for value in item]
        return item

    return strip(normalize_sequence_architecture_mapping(value))


__all__ = ["normalize_sequence_architecture_mapping", "strip_sequence_architecture_payloads"]
