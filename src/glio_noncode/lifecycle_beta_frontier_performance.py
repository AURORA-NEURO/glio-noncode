"""Small deterministic performance budget report for local rehearsal."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_runtime import LifecycleBetaFrontierRuntimeReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierPerformanceBudget:
    budget_id: str
    stage_count: int
    total_duration_ms: float
    max_stage_duration_ms: float
    stage_budget_ms: float
    total_budget_ms: float
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_lifecycle_beta_frontier_performance_budget(runtime: LifecycleBetaFrontierRuntimeReport, *, stage_budget_ms: float = 5000.0, total_budget_ms: float = 30000.0) -> LifecycleBetaFrontierPerformanceBudget:
    if stage_budget_ms <= 0 or total_budget_ms <= 0:
        raise ValueError("performance budgets must be positive")
    durations = tuple(item.duration_ms for item in runtime.stages)
    body = {"budget_id": runtime.run_id, "stage_count": len(durations), "total_duration_ms": round(sum(durations), 3), "max_stage_duration_ms": round(max(durations, default=0.0), 3), "stage_budget_ms": stage_budget_ms, "total_budget_ms": total_budget_ms}
    body["accepted"] = body["max_stage_duration_ms"] <= stage_budget_ms and body["total_duration_ms"] <= total_budget_ms
    return LifecycleBetaFrontierPerformanceBudget(**body, content_address=content_hash(body))


__all__ = ["LifecycleBetaFrontierPerformanceBudget", "build_lifecycle_beta_frontier_performance_budget"]
