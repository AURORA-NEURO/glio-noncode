"""Normalize architecture projections for stable exports and comparisons."""

from __future__ import annotations

from typing import Any


def normalize_specimen_architecture_mapping(value: Any) -> Any:
    """Recursively sort mapping keys and normalize tuple-like values."""

    if isinstance(value, dict):
        return {
            str(key): normalize_specimen_architecture_mapping(value[key])
            for key in sorted(value, key=str)
        }
    if isinstance(value, (tuple, list)):
        return [normalize_specimen_architecture_mapping(item) for item in value]
    if hasattr(value, "value") and isinstance(value.value, str):
        return value.value
    return value


def strip_specimen_architecture_payloads(value: dict[str, Any]) -> dict[str, Any]:
    """Remove raw payload fields from a release-facing projection."""

    result = normalize_specimen_architecture_mapping(value)
    if isinstance(result, dict):
        result.pop("payload", None)
        result.pop("raw_payload", None)
    return result


__all__ = ["normalize_specimen_architecture_mapping", "strip_specimen_architecture_payloads"]
