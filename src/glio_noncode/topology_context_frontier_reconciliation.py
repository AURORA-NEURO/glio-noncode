"""Expected-versus-observed reconciliation for topology states."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_context_frontier_fixture_eval import TopologyContextFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierReconciliationItem:
    record_id: str
    expected_state: str
    observed_state: str
    state_match: bool
    expected_issues: tuple[str, ...]
    observed_issues: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierReconciliation:
    items: tuple[TopologyContextFrontierReconciliationItem, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"items": [item.to_dict() for item in self.items], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def reconcile_topology_context_frontier(
    evaluation: TopologyContextFrontierEvaluation,
) -> TopologyContextFrontierReconciliation:
    items = tuple(
        TopologyContextFrontierReconciliationItem(
            item.record_id,
            item.expected_state,
            item.observed_state,
            item.state_match,
            item.expected_issue_codes,
            item.observed_issue_codes,
        )
        for item in evaluation.rows
    )
    return TopologyContextFrontierReconciliation(
        items=items, accepted=all(item.state_match for item in items)
    )


__all__ = [
    "TopologyContextFrontierReconciliation",
    "TopologyContextFrontierReconciliationItem",
    "reconcile_topology_context_frontier",
]
