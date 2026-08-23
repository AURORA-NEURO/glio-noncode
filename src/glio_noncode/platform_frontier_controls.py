"""Positive/control coverage accounting for C01-C04."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_contracts import PlatformFrontierEvaluation, PlatformFrontierOperation, PlatformFrontierRole
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierControlCoverage:
    operation: PlatformFrontierOperation
    positive_count: int
    control_count: int
    accepted_positive_count: int
    visible_control_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierControlReport:
    rows: tuple[PlatformFrontierControlCoverage, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_platform_frontier_control_coverage(evaluation: PlatformFrontierEvaluation) -> PlatformFrontierControlReport:
    rows = []
    for operation in PlatformFrontierOperation:
        selected = tuple(item for item in evaluation.executions if item.operation is operation)
        positive = tuple(item for item in selected if item.role is PlatformFrontierRole.POSITIVE)
        controls = tuple(item for item in selected if item.role is PlatformFrontierRole.CONTROL)
        body = {"operation": operation, "positive_count": len(positive), "control_count": len(controls), "accepted_positive_count": sum(item.accepted for item in positive), "visible_control_count": sum(not item.accepted for item in controls), "accepted": len(positive) == 1 and len(controls) == 3 and sum(item.accepted for item in positive) == 1 and sum(not item.accepted for item in controls) == 3}
        rows.append(PlatformFrontierControlCoverage(**body, content_address=content_hash(body)))
    return PlatformFrontierControlReport(tuple(rows), all(item.accepted for item in rows), content_hash(tuple(rows)))


__all__ = ["PlatformFrontierControlCoverage", "PlatformFrontierControlReport", "build_platform_frontier_control_coverage"]
