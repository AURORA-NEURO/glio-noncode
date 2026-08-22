"""Requirement-to-evidence traceability for the C01-C04 foundation build."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation
from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierFixture, LinkGraphFoundationFrontierOperation, default_link_graph_foundation_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierTraceabilityItem:
    item_id: str
    operation: str
    requirement: str
    implementation_modules: tuple[str, ...]
    test_modules: tuple[str, ...]
    evidence_addresses: tuple[str, ...]
    accepted: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierTraceabilityReport:
    fixture_id: str
    items: tuple[LinkGraphFoundationFrontierTraceabilityItem, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_items(self) -> tuple[str, ...]:
        return tuple(item.item_id for item in self.items if not item.accepted)

    def for_operation(self, operation: str) -> LinkGraphFoundationFrontierTraceabilityItem:
        return next(item for item in self.items if item.operation == operation)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "items": [item.to_dict() for item in self.items], "failed_items": self.failed_items, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_foundation_frontier_traceability(fixture: LinkGraphFoundationFrontierFixture | None = None, evaluation: LinkGraphFoundationFrontierEvaluation | None = None) -> LinkGraphFoundationFrontierTraceabilityReport:
    value = fixture or default_link_graph_foundation_frontier_fixture()
    replay = evaluation or __import__("glio_noncode.link_graph_foundation_frontier_fixture_eval", fromlist=["evaluate_link_graph_foundation_frontier_fixture"]).evaluate_link_graph_foundation_frontier_fixture(value)
    items = []
    for operation in LinkGraphFoundationFrontierOperation:
        rows = replay.by_operation(operation.value)
        items.append(LinkGraphFoundationFrontierTraceabilityItem(f"trace-{operation.value}", operation.value, f"{operation.value} retains declared outcomes and limitations", ("link_graph_foundation_frontier_public_data", "link_graph_foundation_frontier_adapters", "link_graph_foundation_frontier_pipeline"), ("tests.test_link_graph_foundation_frontier", "tests.test_link_graph_foundation_frontier_depth"), tuple(row.adapter.content_address for row in rows), bool(rows) and all(row.state_match and row.issue_match for row in rows)))
    values = tuple(items)
    return LinkGraphFoundationFrontierTraceabilityReport(value.fixture_id, values, bool(values) and all(item.accepted for item in values))


def traceability_summary(report: LinkGraphFoundationFrontierTraceabilityReport) -> dict[str, Any]:
    return {"fixture_id": report.fixture_id, "item_count": len(report.items), "passed_count": sum(item.accepted for item in report.items), "module_count": len({module for item in report.items for module in item.implementation_modules}), "test_count": len({module for item in report.items for module in item.test_modules}), "accepted": report.accepted}


__all__ = ["LinkGraphFoundationFrontierTraceabilityItem", "LinkGraphFoundationFrontierTraceabilityReport", "build_link_graph_foundation_frontier_traceability", "traceability_summary"]
