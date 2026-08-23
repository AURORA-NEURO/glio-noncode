"""Support directory for operational owners and failure routing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierSupportRoute:
    route_id: str
    issue_prefix: str
    queue: str
    response_hours: int
    escalation: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierSupportDirectory:
    routes: tuple[PlatformFrontierSupportRoute, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_platform_frontier_support_directory() -> PlatformFrontierSupportDirectory:
    specs = (("planning", "no_roles", "planning-review", 24, "platform-owner"), ("workflow", "dependency", "workflow-review", 8, "platform-owner"), ("registry", "tool_", "registry-review", 8, "platform-owner"), ("sandbox", "sandbox_", "security-review", 4, "security-owner"))
    routes = []
    for route_id, issue_prefix, queue, response_hours, escalation in specs:
        body = {"route_id": route_id, "issue_prefix": issue_prefix, "queue": queue, "response_hours": response_hours, "escalation": escalation}
        routes.append(PlatformFrontierSupportRoute(**body, content_address=content_hash(body)))
    return PlatformFrontierSupportDirectory(tuple(routes), len(routes) == 4, content_hash(tuple(routes)))


__all__ = ["PlatformFrontierSupportDirectory", "PlatformFrontierSupportRoute", "default_platform_frontier_support_directory"]
