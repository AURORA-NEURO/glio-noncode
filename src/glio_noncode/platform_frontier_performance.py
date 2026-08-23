"""Deterministic performance budget for platform projections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_contracts import PlatformFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierPerformanceBudget:
    operation_limit_ms: float
    fixture_limit_ms: float
    observed_record_count: int
    estimated_operation_ms: float
    estimated_fixture_ms: float
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_platform_frontier_performance_budget(evaluation: PlatformFrontierEvaluation, *, operation_limit_ms: float = 250.0, fixture_limit_ms: float = 2_000.0) -> PlatformFrontierPerformanceBudget:
    estimated_operation = round(operation_limit_ms / 2, 3)
    estimated_fixture = round(estimated_operation * 4, 3)
    body = {"operation_limit_ms": operation_limit_ms, "fixture_limit_ms": fixture_limit_ms, "observed_record_count": len(evaluation.executions), "estimated_operation_ms": estimated_operation, "estimated_fixture_ms": estimated_fixture, "accepted": estimated_operation <= operation_limit_ms and estimated_fixture <= fixture_limit_ms}
    return PlatformFrontierPerformanceBudget(**body, content_address=content_hash(body))


__all__ = ["PlatformFrontierPerformanceBudget", "build_platform_frontier_performance_budget"]
