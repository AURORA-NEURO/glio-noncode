"""Deterministic performance budget for local deployment evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_contracts import DeploymentFrontierEvaluation
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierPerformanceBudget:
    record_count: int
    check_count: int
    estimated_cpu_ms: int
    estimated_memory_mb: int
    max_cpu_ms: int
    max_memory_mb: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_deployment_frontier_performance_budget(evaluation: DeploymentFrontierEvaluation, *, max_cpu_ms: int = 5000, max_memory_mb: int = 256) -> DeploymentFrontierPerformanceBudget:
    records = len(evaluation.executions)
    checks = len(evaluation.checks)
    body = {"record_count": records, "check_count": checks, "estimated_cpu_ms": records * 4 + checks, "estimated_memory_mb": 32 + records * 2, "max_cpu_ms": max_cpu_ms, "max_memory_mb": max_memory_mb}
    body["accepted"] = body["estimated_cpu_ms"] <= max_cpu_ms and body["estimated_memory_mb"] <= max_memory_mb
    return DeploymentFrontierPerformanceBudget(**body, content_address=deployment_address(body))


__all__ = ["DeploymentFrontierPerformanceBudget", "build_deployment_frontier_performance_budget"]
