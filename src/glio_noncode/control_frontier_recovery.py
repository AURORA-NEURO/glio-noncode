"""Recovery plan for control frontier failure states."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierRecoveryAction:
    action_id: str
    trigger: str
    action: str
    preserve: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierRecoveryPlan:
    actions: tuple[ControlFrontierRecoveryAction, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_control_frontier_recovery_plan() -> ControlFrontierRecoveryPlan:
    specs = (
        ("preserve", "any failure", "retain last accepted addresses", "prior release manifest"),
        ("classify", "failed check", "classify first failed surface", "failing check receipt"),
        ("isolate", "context mismatch", "stop before aggregation", "source and row receipts"),
        ("repair", "schema or adapter failure", "repair declared boundary only", "old version and diff"),
        ("replay", "address mismatch", "rebuild and compare replay", "both address sets"),
        ("review", "blocked or abstained", "route to bounded queue", "issue codes and roles"),
    )
    actions = []
    for action_id, trigger, action, preserve in specs:
        body = {"action_id": action_id, "trigger": trigger, "action": action, "preserve": preserve}
        actions.append(ControlFrontierRecoveryAction(**body, content_address=content_hash(body)))
    return ControlFrontierRecoveryPlan(tuple(actions), True, content_hash(tuple(actions)))


__all__ = ["ControlFrontierRecoveryAction", "ControlFrontierRecoveryPlan", "build_control_frontier_recovery_plan"]
