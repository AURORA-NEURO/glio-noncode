"""Expected-versus-observed comparison cells for link evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation
from .link_graph_foundation_frontier_metrics import LinkGraphFoundationFrontierMetrics, build_link_graph_foundation_frontier_metrics
from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierFixture, default_link_graph_foundation_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierComparisonCell:
    record_id: str
    dimension: str
    expected: Any
    observed: Any
    match: bool
    difference: str = ""

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierComparisonReport:
    fixture_id: str
    cells: tuple[LinkGraphFoundationFrontierComparisonCell, ...]
    expected_record_count: int
    observed_record_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def mismatches(self) -> tuple[LinkGraphFoundationFrontierComparisonCell, ...]:
        return tuple(item for item in self.cells if not item.match)

    def by_dimension(self, dimension: str) -> tuple[LinkGraphFoundationFrontierComparisonCell, ...]:
        return tuple(item for item in self.cells if item.dimension == dimension)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "cells": [item.to_dict() for item in self.cells], "mismatch_count": len(self.mismatches), "expected_record_count": self.expected_record_count, "observed_record_count": self.observed_record_count, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def compare_link_graph_foundation_frontier_fixture(fixture: LinkGraphFoundationFrontierFixture, evaluation: LinkGraphFoundationFrontierEvaluation) -> LinkGraphFoundationFrontierComparisonReport:
    cells = []
    for row in evaluation.rows:
        cells.append(LinkGraphFoundationFrontierComparisonCell(row.record_id, "state", row.expected_state, row.observed_state, row.state_match, "state differs" if not row.state_match else ""))
        cells.append(LinkGraphFoundationFrontierComparisonCell(row.record_id, "issues", row.expected_issue_codes, row.observed_issue_codes, row.issue_match, "issue set differs" if not row.issue_match else ""))
        cells.append(LinkGraphFoundationFrontierComparisonCell(row.record_id, "operation", row.operation, row.adapter.operation, row.operation == row.adapter.operation, "operation differs" if row.operation != row.adapter.operation else ""))
    values = tuple(cells)
    return LinkGraphFoundationFrontierComparisonReport(fixture.fixture_id, values, len(fixture.records), len(evaluation.rows), bool(values) and all(item.match for item in values) and len(fixture.records) == len(evaluation.rows))


def compare_link_graph_foundation_frontier_metrics(left: LinkGraphFoundationFrontierMetrics, right: LinkGraphFoundationFrontierMetrics) -> dict[str, Any]:
    fields = ("record_count", "positive_count", "control_count", "state_counts", "issue_counts", "accepted")
    differences = {field: {"left": getattr(left, field), "right": getattr(right, field)} for field in fields if getattr(left, field) != getattr(right, field)}
    return {"equal": not differences, "differences": differences, "left_address": left.content_address, "right_address": right.content_address}


def build_link_graph_foundation_frontier_comparison(evaluation: LinkGraphFoundationFrontierEvaluation, fixture: LinkGraphFoundationFrontierFixture | None = None) -> LinkGraphFoundationFrontierComparisonReport:
    value = fixture or default_link_graph_foundation_frontier_fixture()
    return compare_link_graph_foundation_frontier_fixture(value, evaluation)


__all__ = ["LinkGraphFoundationFrontierComparisonCell", "LinkGraphFoundationFrontierComparisonReport", "build_link_graph_foundation_frontier_comparison", "compare_link_graph_foundation_frontier_fixture", "compare_link_graph_foundation_frontier_metrics"]
