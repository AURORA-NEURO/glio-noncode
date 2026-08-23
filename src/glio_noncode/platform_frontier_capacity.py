"""Capacity-envelope projection for bounded platform workflow execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_resource_accounting import PlatformFrontierResourceAccounting
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierCapacityLane:
    lane_id: str
    observed: float
    capacity: float
    utilization: float
    headroom: float
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierCapacityReport:
    plan_id: str
    lanes: tuple[PlatformFrontierCapacityLane, ...]
    utilization_limit: float
    accepted: bool
    constrained_lanes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_platform_frontier_capacity_report(
    accounting: PlatformFrontierResourceAccounting,
    *,
    utilization_limit: float = 0.9,
) -> PlatformFrontierCapacityReport:
    """Project resource usage into explicit lanes with a release threshold."""

    if not 0.0 < utilization_limit <= 1.0:
        raise ValueError("utilization_limit must be greater than zero and no greater than one")
    observations = (
        ("cpu", float(accounting.cpu), float(accounting.capacity.get("cpu", 0.0))),
        ("memory_gb", float(accounting.memory_gb), float(accounting.capacity.get("memory_gb", 0.0))),
        ("storage_gb", float(accounting.storage_gb), float(accounting.capacity.get("storage_gb", 0.0))),
        ("gpu_count", float(accounting.gpu_count), float(accounting.capacity.get("gpu_count", 0.0))),
        ("max_seconds", float(accounting.max_seconds), float(accounting.capacity.get("max_seconds", 0.0))),
    )
    lanes = []
    for lane_id, observed, capacity in observations:
        utilization = observed / capacity if capacity > 0 else 1.0
        headroom = max(capacity - observed, 0.0)
        body = {
            "lane_id": lane_id,
            "observed": observed,
            "capacity": capacity,
            "utilization": utilization,
            "headroom": headroom,
            "accepted": capacity > 0 and utilization <= utilization_limit,
        }
        lanes.append(PlatformFrontierCapacityLane(**body, content_address=content_hash(body)))
    constrained = tuple(item.lane_id for item in lanes if not item.accepted)
    body = {
        "plan_id": accounting.plan_id,
        "lanes": tuple(lanes),
        "utilization_limit": utilization_limit,
        "accepted": not constrained,
        "constrained_lanes": constrained,
    }
    return PlatformFrontierCapacityReport(**body, content_address=content_hash(body))


__all__ = [
    "PlatformFrontierCapacityLane",
    "PlatformFrontierCapacityReport",
    "build_platform_frontier_capacity_report",
]
