"""Performance budget declarations for the local control frontier runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_contracts import ControlFrontierOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierPerformanceBudget:
    operation: ControlFrontierOperation
    max_rows: int
    max_seconds: float
    memory_mb: int
    deterministic: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_control_frontier_performance_budget() -> tuple[ControlFrontierPerformanceBudget, ...]:
    rows = []
    for operation in ControlFrontierOperation:
        body = {"operation": operation, "max_rows": 10000, "max_seconds": 5.0, "memory_mb": 512, "deterministic": True}
        rows.append(ControlFrontierPerformanceBudget(**body, content_address=content_hash(body)))
    return tuple(rows)


__all__ = ["ControlFrontierPerformanceBudget", "build_control_frontier_performance_budget"]
