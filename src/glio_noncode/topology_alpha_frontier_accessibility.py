"""Accessible labels and review columns for alpha operation outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierOperationAccessibility:
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
class TopologyAlphaFrontierAccessibilityReport:
    operations: tuple[TopologyAlphaFrontierOperationAccessibility, ...]
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


def evaluate_topology_alpha_frontier_accessibility(evaluation: TopologyAlphaFrontierEvaluation) -> TopologyAlphaFrontierAccessibilityReport:
    labels = {"boundary_motif": "Boundary motif orientations", "ctcf_cohesin": "CTCF and cohesin channel comparison", "idh_insulator": "IDH insulator comparison", "sv_rewire": "SV topology edge simulation"}
    values = tuple(TopologyAlphaFrontierOperationAccessibility(operation, labels[operation], "Context-qualified aggregate results with explicit uncertainty and source receipts.", len(evaluation.by_operation(operation)), len(tuple(item for item in evaluation.by_operation(operation) if item.role == "control")), ("record_id", "operation", "state", "issues", "source_ids", "content_address"), all(item.adapter.content_address for item in evaluation.by_operation(operation))) for operation in sorted({item.operation for item in evaluation.rows}))
    return TopologyAlphaFrontierAccessibilityReport(values, len(values) == 4 and all(item.accessible for item in values))


__all__ = ["TopologyAlphaFrontierAccessibilityReport", "TopologyAlphaFrontierOperationAccessibility", "evaluate_topology_alpha_frontier_accessibility"]
