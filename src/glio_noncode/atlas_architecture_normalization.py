"""Stable and payload-free D05 atlas projections."""

from __future__ import annotations

from typing import Any

from .serialization import jsonable


def normalize_atlas_architecture_mapping(value: Any) -> dict[str, Any]:
    normalized = jsonable(value)
    if not isinstance(normalized, dict):
        raise TypeError("atlas architecture projection must be a mapping")
    return dict(sorted(normalized.items(), key=lambda item: item[0]))


def strip_atlas_architecture_payloads(value: Any) -> dict[str, Any]:
    normalized = normalize_atlas_architecture_mapping(value)

    def strip(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: strip(item)
                for key, item in value.items()
                if key not in {"payload", "raw_payload"}
            }
        if isinstance(value, list):
            return [strip(item) for item in value]
        return value

    return strip(normalized)


__all__ = ["normalize_atlas_architecture_mapping", "strip_atlas_architecture_payloads"]
