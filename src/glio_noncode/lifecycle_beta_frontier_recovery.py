"""Recovery plan for interrupted or failed lifecycle runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_runtime import LifecycleBetaFrontierRuntimeReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierRecoveryAction:
    action_id: str
    failed_stage: str
    restart_stage: str
    preserve_addresses: tuple[str, ...]
    reason: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierRecoveryPlan:
    run_id: str
    actions: tuple[LifecycleBetaFrontierRecoveryAction, ...]
    safe_to_resume: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_lifecycle_beta_frontier_recovery_plan(runtime: LifecycleBetaFrontierRuntimeReport) -> LifecycleBetaFrontierRecoveryPlan:
    actions = []
    for item in runtime.stages:
        body = {"action_id": f"resume:{item.stage_id}", "failed_stage": item.stage_id, "restart_stage": item.stage_id, "preserve_addresses": (item.output_address,), "reason": "stage outputs are immutable and can be replayed from this boundary"}
        actions.append(LifecycleBetaFrontierRecoveryAction(**body, content_address=content_hash(body)))
    return LifecycleBetaFrontierRecoveryPlan(runtime.run_id, tuple(actions), True, content_hash({"run_id": runtime.run_id, "actions": tuple(actions)}))


__all__ = ["LifecycleBetaFrontierRecoveryAction", "LifecycleBetaFrontierRecoveryPlan", "build_lifecycle_beta_frontier_recovery_plan"]
