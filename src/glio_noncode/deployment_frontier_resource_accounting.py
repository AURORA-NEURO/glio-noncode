"""Resource accounting for the deployment frontier execution plan."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_execution_plan import DeploymentFrontierExecutionPlan
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierResourceAccounting:
    plan_id: str
    cpu_units: float
    memory_mb: float
    storage_mb: float
    wall_seconds: int
    capacity: dict[str, float]
    fits: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def account_deployment_frontier_resources(plan: DeploymentFrontierExecutionPlan, *, capacity: dict[str, float] | None = None) -> DeploymentFrontierResourceAccounting:
    capacity = capacity or {"cpu_units": 16.0, "memory_mb": 512.0, "storage_mb": 2048.0, "wall_seconds": 300.0}
    body = {"plan_id": plan.plan_id, "cpu_units": float(len(plan.steps) * 1.5), "memory_mb": float(32 + len(plan.steps) * 16), "storage_mb": float(128 + len(plan.steps) * 64), "wall_seconds": len(plan.steps) * 12, "capacity": capacity}
    body["fits"] = all(body[key] <= float(capacity.get(key, 0.0)) for key in ("cpu_units", "memory_mb", "storage_mb", "wall_seconds"))
    return DeploymentFrontierResourceAccounting(**body, content_address=deployment_address(body))


__all__ = ["DeploymentFrontierResourceAccounting", "account_deployment_frontier_resources"]
