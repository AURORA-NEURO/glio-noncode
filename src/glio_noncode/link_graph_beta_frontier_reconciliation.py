"""Reconcile expected and observed beta-link states and issue codes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_fixture_eval import LinkGraphBetaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierReconciliationItem:
    record_id: str
    state_match: bool
    issue_match: bool
    expected_state: str
    observed_state: str
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]

    @property
    def accepted(self) -> bool:
        return self.state_match and self.issue_match

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierReconciliation:
    items: tuple[LinkGraphBetaFrontierReconciliationItem, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def mismatches(self) -> tuple[str, ...]:
        return tuple(item.record_id for item in self.items if not item.accepted)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"items": [item.to_dict() for item in self.items], "mismatches": self.mismatches, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def reconcile_link_graph_beta_frontier(evaluation: LinkGraphBetaFrontierEvaluation) -> LinkGraphBetaFrontierReconciliation:
    items = tuple(LinkGraphBetaFrontierReconciliationItem(row.record_id, row.state_match, row.issue_match, row.expected_state, row.observed_state, row.expected_issue_codes, row.observed_issue_codes) for row in evaluation.rows)
    return LinkGraphBetaFrontierReconciliation(items, bool(items) and all(item.accepted for item in items))


__all__ = ["LinkGraphBetaFrontierReconciliation", "LinkGraphBetaFrontierReconciliationItem", "reconcile_link_graph_beta_frontier"]
