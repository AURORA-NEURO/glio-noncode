"""Stable release projections for D04 reference architecture."""

from __future__ import annotations

from typing import Any


def normalize_reference_architecture_mapping(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): normalize_reference_architecture_mapping(value[key])
            for key in sorted(value, key=str)
        }
    if isinstance(value, (list, tuple)):
        return [normalize_reference_architecture_mapping(item) for item in value]
    if hasattr(value, "value") and isinstance(value.value, str):
        return value.value
    return value


def strip_reference_architecture_payloads(value: dict[str, Any]) -> dict[str, Any]:
    result = normalize_reference_architecture_mapping(value)
    if isinstance(result, dict):
        result.pop("payload", None)
        result.pop("raw_payload", None)
    return result


__all__ = ["normalize_reference_architecture_mapping", "strip_reference_architecture_payloads"]
