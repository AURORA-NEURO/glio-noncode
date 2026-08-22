"""Accessible review labels and operation summaries for release consumers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_beta_frontier_fixture_eval import TopologyBetaFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierOperationAccessibility:
    operation: str
    label: str
    summary: str
    state_count: int
    review_count: int
    table_columns: tuple[str, ...]
    accessible: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierAccessibilityReport:
    operations: tuple[TopologyBetaFrontierOperationAccessibility, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"operations": [item.to_dict() for item in self.operations], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def evaluate_topology_beta_frontier_accessibility(evaluation: TopologyBetaFrontierEvaluation) -> TopologyBetaFrontierAccessibilityReport:
    labels = {"loop_stripe": "Loop and stripe features", "promoter_capture": "Promoter capture contacts", "enhancer_promoter_contact": "Enhancer promoter contact evidence", "activity_by_contact": "Activity by contact components"}
    values = []
    for operation in sorted({item.operation for item in evaluation.rows}):
        rows = tuple(item for item in evaluation.rows if item.operation == operation)
        values.append(TopologyBetaFrontierOperationAccessibility(operation, labels[operation], "Context-qualified aggregate observations with source receipts.", len(rows), sum(item.role == "control" for item in rows), ("record_id", "operation", "state", "issues", "source_ids", "content_address"), bool(rows) and all(item.adapter.content_address for item in rows)))
    return TopologyBetaFrontierAccessibilityReport(tuple(values), bool(values) and all(item.accessible for item in values))


__all__ = ["TopologyBetaFrontierAccessibilityReport", "TopologyBetaFrontierOperationAccessibility", "evaluate_topology_beta_frontier_accessibility"]
