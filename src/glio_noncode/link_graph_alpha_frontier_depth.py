"""Depth accounting for the four Domain 10 link modules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_fixture_eval import LinkGraphAlphaFrontierEvaluation
from .link_graph_alpha_frontier_public_data import LinkGraphAlphaFrontierFixture, LinkGraphAlphaFrontierOperation
from .link_graph_alpha_frontier_support import check
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierDepthDimension:
    dimension_id: str
    operation: str
    record_count: int
    positive_count: int
    control_count: int
    expected_states: tuple[str, ...]
    issue_codes: tuple[str, ...]
    implementation_notes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierDepthReport:
    dimensions: tuple[LinkGraphAlphaFrontierDepthDimension, ...]
    checks: tuple[Any, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_operation(self, operation: str) -> LinkGraphAlphaFrontierDepthDimension:
        for item in self.dimensions:
            if item.operation == operation:
                return item
        raise KeyError(operation)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"dimensions": [item.to_dict() for item in self.dimensions], "checks": [item.to_dict() for item in self.checks], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def audit_link_graph_alpha_frontier_depth(fixture: LinkGraphAlphaFrontierFixture, evaluation: LinkGraphAlphaFrontierEvaluation) -> LinkGraphAlphaFrontierDepthReport:
    notes = {
        LinkGraphAlphaFrontierOperation.CRISPR_PERTURBATION.value: ("direction is retained", "weak support is visible", "opposing evidence is not collapsed"),
        LinkGraphAlphaFrontierOperation.CONTACT_3D.value: ("contact is normalized", "resolution is retained", "alternative genes remain visible"),
        LinkGraphAlphaFrontierOperation.PROMOTER_TETHERING.value: ("distance prior is explicit", "missing components abstain", "ties remain ambiguous"),
        LinkGraphAlphaFrontierOperation.MULTI_GENE_GRAPH.value: ("edges retain evidence paths", "connected components are reported", "contradiction is visible"),
    }
    dimensions = []
    for operation in LinkGraphAlphaFrontierOperation:
        records = fixture.operation_records(operation)
        rows = evaluation.by_operation(operation.value)
        dimensions.append(LinkGraphAlphaFrontierDepthDimension(f"depth:{operation.value}", operation.value, len(records), sum(item.role.value == "positive" for item in records), sum(item.role.value == "control" for item in records), tuple(sorted({item.observed_state for item in rows})), tuple(sorted({code for item in rows for code in item.observed_issue_codes})), notes[operation.value]))
    values = tuple(dimensions)
    checks = (check("four_operations", len(values) == 4, "each link operation has a depth dimension"), check("positive_controls", all(item.positive_count == 1 and item.control_count == 3 for item in values), "each operation has one positive and three controls"), check("state_variety", all(len(item.expected_states) >= 2 for item in values), "each operation demonstrates more than one state"), check("limitations_present", all(item.implementation_notes for item in values), "each operation declares implementation notes"))
    return LinkGraphAlphaFrontierDepthReport(values, checks, all(item.passed for item in checks))


__all__ = ["LinkGraphAlphaFrontierDepthDimension", "LinkGraphAlphaFrontierDepthReport", "audit_link_graph_alpha_frontier_depth"]
