"""Resource accounting for compiled platform workflow steps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .mission_runtime import MissionPlan
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierResourceAccounting:
    plan_id: str
    cpu: float
    memory_gb: float
    storage_gb: float
    gpu_count: int
    max_seconds: int
    network_steps: int
    nondeterministic_steps: int
    capacity: dict[str, float]
    fits: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def account_platform_frontier_resources(plan: MissionPlan, *, capacity: dict[str, float] | None = None) -> PlatformFrontierResourceAccounting:
    capacity = capacity or {"cpu": 16.0, "memory_gb": 32.0, "storage_gb": 100.0, "gpu_count": 4.0, "max_seconds": 3_600.0}
    steps = plan.workflow.steps if plan.workflow else ()
    values = {"cpu": sum(item.resource.cpu for item in steps), "memory_gb": max((item.resource.memory_gb for item in steps), default=0.0), "storage_gb": sum(item.resource.storage_gb for item in steps), "gpu_count": sum(item.resource.gpu_count for item in steps), "max_seconds": sum(item.resource.max_seconds for item in steps)}
    fits = all(values[key] <= float(capacity.get(key, 0.0)) for key in values)
    body = {"plan_id": plan.plan_id, **values, "network_steps": sum(item.resource.network_egress for item in steps), "nondeterministic_steps": sum(not item.deterministic for item in steps), "capacity": capacity, "fits": fits}
    return PlatformFrontierResourceAccounting(**body, content_address=content_hash(body))


__all__ = ["PlatformFrontierResourceAccounting", "account_platform_frontier_resources"]
