"""Read-only inspection views for operation, record, and issue queries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation, TopologyAlphaFrontierEvaluationRow


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierInspectionItem:
    record_id: str
    operation: str
    role: str
    state: str
    issue_codes: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    result_address: str
    disposition: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierInspectionReport:
    items: tuple[TopologyAlphaFrontierInspectionItem, ...]
    query: dict[str, Any]
    matched_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def states(self) -> dict[str, int]:
        return {state: sum(item.state == state for item in self.items) for state in sorted({item.state for item in self.items})}

    def for_operation(self, operation: str) -> tuple[TopologyAlphaFrontierInspectionItem, ...]:
        return tuple(item for item in self.items if item.operation == operation)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"items": [item.to_dict() for item in self.items], "query": self.query, "matched_count": self.matched_count, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _item(row: TopologyAlphaFrontierEvaluationRow) -> TopologyAlphaFrontierInspectionItem:
    disposition = "supported" if row.observed_state == "supported" else "review"
    return TopologyAlphaFrontierInspectionItem(row.record_id, row.operation, row.role, row.observed_state, row.observed_issue_codes, row.adapter.evidence_ids, row.adapter.source_ids, row.adapter.content_address, disposition)


def inspect_topology_alpha_frontier(evaluation: TopologyAlphaFrontierEvaluation, *, operation: str | None = None, state: str | None = None, role: str | None = None, issue_code: str | None = None) -> TopologyAlphaFrontierInspectionReport:
    query = {"operation": operation, "state": state, "role": role, "issue_code": issue_code}
    items = tuple(_item(row) for row in evaluation.rows if (operation is None or row.operation == operation) and (state is None or row.observed_state == state) and (role is None or row.role == role) and (issue_code is None or issue_code in row.observed_issue_codes))
    return TopologyAlphaFrontierInspectionReport(items, query, len(items), all(item.result_address.startswith("sha256:") for item in items))


__all__ = ["TopologyAlphaFrontierInspectionItem", "TopologyAlphaFrontierInspectionReport", "inspect_topology_alpha_frontier"]
