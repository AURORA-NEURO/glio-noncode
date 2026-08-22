"""Expected-versus-observed comparison cells for beta frontier outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_fixture_eval import LinkGraphBetaFrontierEvaluation
from .link_graph_beta_frontier_metrics import LinkGraphBetaFrontierMetrics
from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierFixture, default_link_graph_beta_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierComparisonCell:
    record_id: str
    dimension: str
    expected: Any
    observed: Any
    match: bool
    difference: str = ""

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierComparisonReport:
    fixture_id: str
    cells: tuple[LinkGraphBetaFrontierComparisonCell, ...]
    expected_record_count: int
    observed_record_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def mismatches(self) -> tuple[LinkGraphBetaFrontierComparisonCell, ...]:
        return tuple(item for item in self.cells if not item.match)

    def by_dimension(self, dimension: str) -> tuple[LinkGraphBetaFrontierComparisonCell, ...]:
        return tuple(item for item in self.cells if item.dimension == dimension)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "cells": [item.to_dict() for item in self.cells], "mismatch_count": len(self.mismatches), "expected_record_count": self.expected_record_count, "observed_record_count": self.observed_record_count, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_beta_frontier_comparison(evaluation: LinkGraphBetaFrontierEvaluation, fixture: LinkGraphBetaFrontierFixture | None = None) -> LinkGraphBetaFrontierComparisonReport:
    value = fixture or default_link_graph_beta_frontier_fixture()
    cells = []
    for row in evaluation.rows:
        cells.extend((LinkGraphBetaFrontierComparisonCell(row.record_id, "state", row.expected_state, row.observed_state, row.state_match, "state differs" if not row.state_match else ""), LinkGraphBetaFrontierComparisonCell(row.record_id, "issues", row.expected_issue_codes, row.observed_issue_codes, row.issue_match, "issue set differs" if not row.issue_match else ""), LinkGraphBetaFrontierComparisonCell(row.record_id, "operation", row.operation, row.adapter.operation.value, row.operation == row.adapter.operation.value, "operation differs" if row.operation != row.adapter.operation.value else "")))
    values = tuple(cells)
    return LinkGraphBetaFrontierComparisonReport(value.fixture_id, values, len(value.records), len(evaluation.rows), bool(values) and all(item.match for item in values) and len(value.records) == len(evaluation.rows))


def compare_link_graph_beta_frontier_metrics(left: LinkGraphBetaFrontierMetrics, right: LinkGraphBetaFrontierMetrics) -> dict[str, Any]:
    fields = ("record_count", "positive_count", "control_count", "state_counts", "issue_counts", "accepted")
    differences = {field: {"left": getattr(left, field), "right": getattr(right, field)} for field in fields if getattr(left, field) != getattr(right, field)}
    return {"equal": not differences, "differences": differences, "left_address": left.content_address, "right_address": right.content_address}


__all__ = ["LinkGraphBetaFrontierComparisonCell", "LinkGraphBetaFrontierComparisonReport", "build_link_graph_beta_frontier_comparison", "compare_link_graph_beta_frontier_metrics"]
