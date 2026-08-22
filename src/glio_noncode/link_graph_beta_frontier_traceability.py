"""Requirement-to-evidence traceability for C05-C08."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_fixture_eval import LinkGraphBetaFrontierEvaluation
from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierFixture, LinkGraphBetaFrontierOperation, default_link_graph_beta_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierTraceabilityItem:
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
class LinkGraphBetaFrontierTraceabilityReport:
    fixture_id: str
    items: tuple[LinkGraphBetaFrontierTraceabilityItem, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_items(self) -> tuple[str, ...]:
        return tuple(item.item_id for item in self.items if not item.accepted)

    def for_operation(self, operation: str) -> LinkGraphBetaFrontierTraceabilityItem:
        return next(item for item in self.items if item.operation == operation)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "items": [item.to_dict() for item in self.items], "failed_items": self.failed_items, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_beta_frontier_traceability(fixture: LinkGraphBetaFrontierFixture | None = None, evaluation: LinkGraphBetaFrontierEvaluation | None = None) -> LinkGraphBetaFrontierTraceabilityReport:
    value = fixture or default_link_graph_beta_frontier_fixture()
    replay = evaluation or __import__("glio_noncode.link_graph_beta_frontier_fixture_eval", fromlist=["evaluate_link_graph_beta_frontier_fixture"]).evaluate_link_graph_beta_frontier_fixture(value)
    items = tuple(LinkGraphBetaFrontierTraceabilityItem(f"trace-{operation.value}", operation.value, f"{operation.value} preserves exact context, receipts, and limitations", ("link_graph_beta_frontier_public_data", "link_graph_beta_frontier_adapters", "link_graph_beta_frontier_pipeline"), ("tests.test_link_graph_beta_frontier", "tests.test_link_graph_beta_frontier_depth"), tuple(row.adapter.content_address for row in replay.by_operation(operation.value)), bool(replay.by_operation(operation.value)) and all(row.state_match and row.issue_match for row in replay.by_operation(operation.value))) for operation in LinkGraphBetaFrontierOperation)
    return LinkGraphBetaFrontierTraceabilityReport(value.fixture_id, items, bool(items) and all(item.accepted for item in items))


def traceability_summary(report: LinkGraphBetaFrontierTraceabilityReport) -> dict[str, Any]:
    return {"fixture_id": report.fixture_id, "item_count": len(report.items), "passed_count": sum(item.accepted for item in report.items), "module_count": len({module for item in report.items for module in item.implementation_modules}), "test_count": len({module for item in report.items for module in item.test_modules}), "accepted": report.accepted}


__all__ = ["LinkGraphBetaFrontierTraceabilityItem", "LinkGraphBetaFrontierTraceabilityReport", "build_link_graph_beta_frontier_traceability", "traceability_summary"]
