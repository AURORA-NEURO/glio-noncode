"""Typed next actions for every control and non-supported alpha row."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierReviewAction:
    action_id: str
    record_id: str
    operation: str
    priority: str
    trigger_codes: tuple[str, ...]
    next_action: str
    exit_condition: str
    release_effect: str
    status: str = "open"

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierReviewActionPlan:
    actions: tuple[TopologyAlphaFrontierReviewAction, ...]
    open_count: int
    high_priority_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_record(self, record_id: str) -> TopologyAlphaFrontierReviewAction:
        for item in self.actions:
            if item.record_id == record_id:
                return item
        raise KeyError(record_id)

    def for_priority(self, priority: str) -> tuple[TopologyAlphaFrontierReviewAction, ...]:
        return tuple(item for item in self.actions if item.priority == priority)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"actions": [item.to_dict() for item in self.actions], "open_count": self.open_count, "high_priority_count": self.high_priority_count, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _action_for(row: Any) -> tuple[str, str, str]:
    if "context_mismatch" in row.observed_issue_codes:
        return "high", "verify exact context before transport", "context receipt matches the target context"
    if row.observed_state == "ambiguous":
        return "high", "inspect competing measurements and retain both paths", "independent evidence resolves or preserves disagreement"
    if row.observed_state == "partial":
        return "medium", "request the missing operation field or source receipt", "required field is present or explicit missingness is accepted"
    return "low", "retain the positive path as descriptive aggregate evidence", "release scope remains unchanged"


def build_topology_alpha_frontier_review_actions(evaluation: TopologyAlphaFrontierEvaluation) -> TopologyAlphaFrontierReviewActionPlan:
    actions = []
    for row in evaluation.rows:
        priority, next_action, exit_condition = _action_for(row)
        actions.append(TopologyAlphaFrontierReviewAction(f"action-{row.record_id}", row.record_id, row.operation, priority, row.observed_issue_codes, next_action, exit_condition, "block qualified interpretation" if priority == "high" else "retain descriptive review"))
    values = tuple(actions)
    return TopologyAlphaFrontierReviewActionPlan(values, sum(item.status == "open" for item in values), sum(item.priority == "high" for item in values), len(values) == 16 and all(item.next_action and item.exit_condition for item in values))


__all__ = ["TopologyAlphaFrontierReviewAction", "TopologyAlphaFrontierReviewActionPlan", "build_topology_alpha_frontier_review_actions"]
