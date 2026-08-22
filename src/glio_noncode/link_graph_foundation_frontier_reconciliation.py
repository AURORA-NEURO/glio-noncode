"""Expected and observed state reconciliation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation
from .link_graph_foundation_frontier_support import check
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierReconciliationItem:
    record_id: str
    state_match: bool
    issue_match: bool
    measurement_present: bool
    missing_issue_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierReconciliation:
    items: tuple[LinkGraphFoundationFrontierReconciliationItem, ...]
    checks: tuple[Any, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def mismatches(self) -> tuple[LinkGraphFoundationFrontierReconciliationItem, ...]:
        return tuple(item for item in self.items if not item.state_match or not item.issue_match or not item.measurement_present)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"items": [item.to_dict() for item in self.items], "mismatches": [item.to_dict() for item in self.mismatches], "checks": [item.to_dict() for item in self.checks], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def reconcile_link_graph_foundation_frontier(evaluation: LinkGraphFoundationFrontierEvaluation) -> LinkGraphFoundationFrontierReconciliation:
    items = tuple(LinkGraphFoundationFrontierReconciliationItem(row.record_id, row.state_match, row.issue_match, isinstance(row.adapter.measurements, dict), tuple(sorted(set(row.expected_issue_codes) - set(row.observed_issue_codes)))) for row in evaluation.rows)
    checks = (check("rows", len(items) == len(evaluation.rows), "reconciliation rows align"), check("states", all(item.state_match for item in items), "states match"), check("issues", all(item.issue_match for item in items), "issues match"), check("measurements", all(item.measurement_present for item in items), "measurements are mapped"))
    return LinkGraphFoundationFrontierReconciliation(items, checks, all(item.passed for item in checks))


__all__ = ["LinkGraphFoundationFrontierReconciliation", "LinkGraphFoundationFrontierReconciliationItem", "reconcile_link_graph_foundation_frontier"]
