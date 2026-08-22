"""Canonical manifest serialization and round-trip helpers."""

from __future__ import annotations

import json
from typing import Any

from .serialization import jsonable


def serialize_link_graph_alpha_frontier_manifest(value: Any) -> str:
    payload = value.to_dict() if hasattr(value, "to_dict") else value
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def deserialize_link_graph_alpha_frontier_manifest(payload: str) -> dict[str, Any]:
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise ValueError("manifest must decode to an object")
    return value


def round_trip_link_graph_alpha_frontier_manifest(value: Any) -> bool:
    payload = value.to_dict() if hasattr(value, "to_dict") else value
    return deserialize_link_graph_alpha_frontier_manifest(serialize_link_graph_alpha_frontier_manifest(payload)) == jsonable(payload)


__all__ = ["deserialize_link_graph_alpha_frontier_manifest", "round_trip_link_graph_alpha_frontier_manifest", "serialize_link_graph_alpha_frontier_manifest"]
