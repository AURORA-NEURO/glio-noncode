"""Change-control receipt for versioned control frontier fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_contracts import CONTROL_FRONTIER_VERSION
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierChangeControl:
    change_id: str
    current_version: str
    allowed_change_types: tuple[str, ...]
    required_reviews: tuple[str, ...]
    rollback_rule: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_control_frontier_change_control() -> ControlFrontierChangeControl:
    body = {"change_id": "control-frontier-change-control", "current_version": CONTROL_FRONTIER_VERSION, "allowed_change_types": ("fixture-additive", "schema-additive", "policy-tightening", "documentation"), "required_reviews": ("platform_reviewer", "provenance_reviewer", "release_reviewer"), "rollback_rule": "retain prior content address and withdraw the candidate manifest"}
    return ControlFrontierChangeControl(**body, content_address=content_hash(body))


__all__ = ["ControlFrontierChangeControl", "default_control_frontier_change_control"]
