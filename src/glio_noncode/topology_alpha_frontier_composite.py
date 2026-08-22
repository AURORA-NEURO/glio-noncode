"""Cross-operation composite summaries that preserve operation boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierCompositeOperation:
    operation: str
    record_count: int
    supported_count: int
    review_count: int
    state_counts: dict[str, int]
    issue_codes: tuple[str, ...]
    evidence_count: int
    descriptive_only: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierCompositeReport:
    operations: tuple[TopologyAlphaFrontierCompositeOperation, ...]
    cross_operation_links: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def operation(self, name: str) -> TopologyAlphaFrontierCompositeOperation:
        for item in self.operations:
            if item.operation == name:
                return item
        raise KeyError(name)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"operations": [item.to_dict() for item in self.operations], "cross_operation_links": self.cross_operation_links, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_alpha_frontier_composite(evaluation: TopologyAlphaFrontierEvaluation) -> TopologyAlphaFrontierCompositeReport:
    operations = []
    for operation in sorted({item.operation for item in evaluation.rows}):
        rows = evaluation.by_operation(operation)
        operations.append(TopologyAlphaFrontierCompositeOperation(operation, len(rows), sum(row.observed_state == "supported" for row in rows), sum(row.role == "control" for row in rows), {state: sum(row.observed_state == state for row in rows) for state in sorted({row.observed_state for row in rows})}, tuple(sorted({code for row in rows for code in row.observed_issue_codes})), sum(len(row.adapter.evidence_ids) for row in rows), True))
    links = tuple({"left_operation": left.operation, "right_operation": right.operation, "shared_context": True, "shared_source_boundary": True, "interpretation": "parallel aggregate summaries; no causal merge"} for left, right in zip(operations, operations[1:]))
    return TopologyAlphaFrontierCompositeReport(tuple(operations), links, len(operations) == 4 and all(item.descriptive_only for item in operations))


__all__ = ["TopologyAlphaFrontierCompositeOperation", "TopologyAlphaFrontierCompositeReport", "build_topology_alpha_frontier_composite"]
