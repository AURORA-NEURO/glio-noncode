"""Recovery plan for platform-control failure states."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierRecoveryAction:
    action_id: str
    trigger: str
    action: str
    preserve: str
    release_blocked: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierRecoveryPlan:
    actions: tuple[PlatformFrontierRecoveryAction, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_platform_frontier_recovery_plan() -> PlatformFrontierRecoveryPlan:
    specs = (("scope", "unknown role or tool", "stop before execution", "original request", True), ("cycle", "workflow cycle", "retain graph and route review", "workflow payload", True), ("privacy", "direct identifier", "reject and redact output", "policy receipt", True), ("address", "receipt mismatch", "rebuild and compare", "both address sets", True), ("review", "control path", "retain bounded queue item", "issue code", False), ("release", "all checks pass", "publish aggregate manifest", "quality and replay", False))
    actions = []
    for action_id, trigger, action, preserve, release_blocked in specs:
        body = {"action_id": action_id, "trigger": trigger, "action": action, "preserve": preserve, "release_blocked": release_blocked}
        actions.append(PlatformFrontierRecoveryAction(**body, content_address=content_hash(body)))
    return PlatformFrontierRecoveryPlan(tuple(actions), len(actions) == 6, content_hash(tuple(actions)))


__all__ = ["PlatformFrontierRecoveryAction", "PlatformFrontierRecoveryPlan", "build_platform_frontier_recovery_plan"]
