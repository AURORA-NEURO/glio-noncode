"""Declared state transitions for positive, control, and boundary paths."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_fixture_eval import LinkGraphAlphaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierStateTransition:
    transition_id: str
    operation: str
    from_state: str
    to_state: str
    trigger: str
    record_ids: tuple[str, ...]
    boundary_effect: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierStateTransitionReport:
    transitions: tuple[LinkGraphAlphaFrontierStateTransition, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"transitions": [item.to_dict() for item in self.transitions], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_alpha_frontier_state_transitions(evaluation: LinkGraphAlphaFrontierEvaluation) -> LinkGraphAlphaFrontierStateTransitionReport:
    transitions = []
    for operation in sorted({row.operation for row in evaluation.rows}):
        rows = evaluation.by_operation(operation)
        positive = next(row for row in rows if row.role == "positive")
        for row in rows:
            if row.observed_state != positive.observed_state:
                transitions.append(LinkGraphAlphaFrontierStateTransition(content_hash((operation, positive.record_id, row.record_id)), operation, positive.observed_state, row.observed_state, ",".join(row.observed_issue_codes) or "control", (positive.record_id, row.record_id), "state change is a control boundary, not a biological effect"))
    values = tuple(transitions)
    return LinkGraphAlphaFrontierStateTransitionReport(values, bool(values) and all("not" in item.boundary_effect for item in values))


__all__ = ["LinkGraphAlphaFrontierStateTransition", "LinkGraphAlphaFrontierStateTransitionReport", "build_link_graph_alpha_frontier_state_transitions"]
