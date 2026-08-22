"""Depth dimensions for the four baseline operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation
from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierFixture, LinkGraphFoundationFrontierOperation
from .link_graph_foundation_frontier_support import check
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierDepthDimension:
    operation: str
    record_count: int
    positive_count: int
    control_count: int
    states: tuple[str, ...]
    issue_codes: tuple[str, ...]
    depth_notes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierDepthReport:
    dimensions: tuple[LinkGraphFoundationFrontierDepthDimension, ...]
    checks: tuple[Any, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_operation(self, operation: str) -> LinkGraphFoundationFrontierDepthDimension:
        for item in self.dimensions:
            if item.operation == operation:
                return item
        raise KeyError(operation)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"dimensions": [item.to_dict() for item in self.dimensions], "checks": [item.to_dict() for item in self.checks], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def audit_link_graph_foundation_frontier_depth(fixture: LinkGraphFoundationFrontierFixture, evaluation: LinkGraphFoundationFrontierEvaluation) -> LinkGraphFoundationFrontierDepthReport:
    notes = {"coordinate_overlap": ("interval overlap is explicit", "multiple elements remain ambiguous", "no overlap is not negative mechanism evidence"), "nearest_gene": ("distance is retained", "ties are visible", "distance windows abstain"), "ccre_assignment": ("cCRE type is explicit", "one-to-many assignment is visible", "foreign context is gated"), "enhancer_gene_consensus": ("method identity is retained", "single methods remain partial", "contradictions remain explicit")}
    dimensions = tuple(LinkGraphFoundationFrontierDepthDimension(operation.value, len(records := fixture.operation_records(operation)), sum(item.role.value == "positive" for item in records), sum(item.role.value == "control" for item in records), tuple(sorted({row.observed_state for row in evaluation.by_operation(operation.value)})), tuple(sorted({code for row in evaluation.by_operation(operation.value) for code in row.observed_issue_codes})), notes[operation.value]) for operation in LinkGraphFoundationFrontierOperation)
    checks = (check("operations", len(dimensions) == 4, "four operations have dimensions"), check("balance", all(item.positive_count == 1 and item.control_count == 3 for item in dimensions), "each operation is balanced"), check("states", all(len(item.states) >= 2 for item in dimensions), "state variety is shown"), check("notes", all(item.depth_notes for item in dimensions), "limitations are declared"))
    return LinkGraphFoundationFrontierDepthReport(dimensions, checks, all(item.passed for item in checks))


__all__ = ["LinkGraphFoundationFrontierDepthDimension", "LinkGraphFoundationFrontierDepthReport", "audit_link_graph_foundation_frontier_depth"]
