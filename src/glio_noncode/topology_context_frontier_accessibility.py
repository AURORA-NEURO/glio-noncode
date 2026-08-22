"""Human-readable review accessibility checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_context_frontier_fixture_eval import TopologyContextFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierOperationAccessibility:
    operation: str
    row_count: int
    labels_present: bool
    states_present: bool
    accessible: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierAccessibilityReport:
    operations: tuple[TopologyContextFrontierOperationAccessibility, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {
            "operations": [item.to_dict() for item in self.operations],
            "accepted": self.accepted,
        }
        if include_address:
            value["content_address"] = self.content_address
        return value


def evaluate_topology_context_frontier_accessibility(
    evaluation: TopologyContextFrontierEvaluation,
) -> TopologyContextFrontierAccessibilityReport:
    operations = tuple(
        TopologyContextFrontierOperationAccessibility(
            operation,
            len(rows),
            all(bool(item.operation) for item in rows),
            all(bool(item.observed_state) for item in rows),
            bool(rows) and all(bool(item.operation) and bool(item.observed_state) for item in rows),
        )
        for operation in sorted({item.operation for item in evaluation.rows})
        for rows in (evaluation.by_operation(operation),)
    )
    return TopologyContextFrontierAccessibilityReport(
        operations, all(item.accessible for item in operations)
    )


__all__ = [
    "TopologyContextFrontierAccessibilityReport",
    "TopologyContextFrontierOperationAccessibility",
    "evaluate_topology_context_frontier_accessibility",
]
