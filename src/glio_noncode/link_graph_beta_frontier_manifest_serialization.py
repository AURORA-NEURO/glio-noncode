"""Stable manifest serialization helpers for beta release outputs."""

from __future__ import annotations

import json
from typing import Any

from .serialization import content_hash, jsonable


def serialize_link_graph_beta_frontier_manifest(value: Any) -> str:
    return json.dumps(jsonable(value), sort_keys=True, indent=2)


def deserialize_link_graph_beta_frontier_manifest(text: str) -> dict[str, Any]:
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("manifest must decode to an object")
    return value


def manifest_serialization_address(value: Any) -> str:
    return content_hash(jsonable(value))


__all__ = ["deserialize_link_graph_beta_frontier_manifest", "manifest_serialization_address", "serialize_link_graph_beta_frontier_manifest"]
