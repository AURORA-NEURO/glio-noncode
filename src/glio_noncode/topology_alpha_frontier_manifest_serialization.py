"""Canonical serialization helpers for alpha manifests and review rows."""

from __future__ import annotations

import json
from typing import Any, Mapping

from .serialization import content_hash, jsonable


def canonical_topology_alpha_frontier_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(jsonable(dict(payload)), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def pretty_topology_alpha_frontier_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(jsonable(dict(payload)), sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def address_topology_alpha_frontier_payload(payload: Mapping[str, Any]) -> str:
    return content_hash(jsonable(dict(payload)))


def serialize_topology_alpha_frontier_record(record: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(jsonable(dict(record)))
    value["content_address"] = address_topology_alpha_frontier_payload(value)
    return value


def serialize_topology_alpha_frontier_rows(rows: list[Mapping[str, Any]]) -> str:
    return pretty_topology_alpha_frontier_json({"rows": [serialize_topology_alpha_frontier_record(row) for row in rows], "row_count": len(rows)})


__all__ = ["address_topology_alpha_frontier_payload", "canonical_topology_alpha_frontier_json", "pretty_topology_alpha_frontier_json", "serialize_topology_alpha_frontier_record", "serialize_topology_alpha_frontier_rows"]
