"""Support routes for public control frontier review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierSupportRoute:
    route_id: str
    trigger: str
    owner_role: str
    evidence_required: tuple[str, ...]
    response_window_hours: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierSupportDirectory:
    routes: tuple[ControlFrontierSupportRoute, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_control_frontier_support_directory() -> ControlFrontierSupportDirectory:
    specs = (("boundary", "context mismatch", "provenance_reviewer", ("source IDs", "context key"), 4), ("policy", "policy blocker", "platform_reviewer", ("policy receipt", "issue codes"), 4), ("runtime", "ledger or replay failure", "runtime_reviewer", ("event ledger", "replay address"), 8), ("release", "release gate failure", "release_reviewer", ("quality receipt", "release manifest"), 24))
    routes = []
    for route_id, trigger, owner_role, evidence_required, response_window_hours in specs:
        body = {"route_id": route_id, "trigger": trigger, "owner_role": owner_role, "evidence_required": evidence_required, "response_window_hours": response_window_hours}
        routes.append(ControlFrontierSupportRoute(**body, content_address=content_hash(body)))
    return ControlFrontierSupportDirectory(tuple(routes), True, content_hash(tuple(routes)))


__all__ = ["ControlFrontierSupportDirectory", "ControlFrontierSupportRoute", "default_control_frontier_support_directory"]
