"""Inspection table with deterministic filters for human review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_beta_frontier_fixture_eval import TopologyBetaFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierInspectionRow:
    record_id: str
    operation: str
    role: str
    state: str
    review_priority: str
    issue_codes: tuple[str, ...]
    source_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    measurements: dict[str, Any]
    next_action: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierInspectionReport:
    rows: tuple[TopologyBetaFrontierInspectionRow, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def filter(self, *, operation: str | None = None, state: str | None = None, role: str | None = None) -> tuple[TopologyBetaFrontierInspectionRow, ...]:
        return tuple(item for item in self.rows if (operation is None or item.operation == operation) and (state is None or item.state == state) and (role is None or item.role == role))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"rows": [item.to_dict() for item in self.rows], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_beta_frontier_inspection(evaluation: TopologyBetaFrontierEvaluation) -> TopologyBetaFrontierInspectionReport:
    rows = []
    for item in evaluation.rows:
        if item.observed_state == "supported" and item.role == "positive":
            priority, action = "low", "retain as aggregate support with receipts"
        elif item.observed_state in {"ambiguous", "out_of_domain"}:
            priority, action = "high", "review context and competing observations"
        else:
            priority, action = "medium", "review missingness or metadata boundary"
        rows.append(TopologyBetaFrontierInspectionRow(item.record_id, item.operation, item.role, item.observed_state, priority, item.observed_issue_codes, item.adapter.source_ids, item.adapter.evidence_ids, item.adapter.measurements, action))
    values = tuple(rows)
    return TopologyBetaFrontierInspectionReport(values, len(values) == len(evaluation.rows) and all(item.next_action for item in values))


def summarize_topology_beta_frontier_inspection(report: TopologyBetaFrontierInspectionReport) -> dict[str, Any]:
    return {"row_count": len(report.rows), "accepted": report.accepted, "priority_counts": {priority: len(tuple(item for item in report.rows if item.review_priority == priority)) for priority in sorted({item.review_priority for item in report.rows})}, "state_counts": {state: len(report.filter(state=state)) for state in sorted({item.state for item in report.rows})}, "operation_counts": {operation: len(report.filter(operation=operation)) for operation in sorted({item.operation for item in report.rows})}}


__all__ = ["TopologyBetaFrontierInspectionReport", "TopologyBetaFrontierInspectionRow", "build_topology_beta_frontier_inspection", "summarize_topology_beta_frontier_inspection"]
