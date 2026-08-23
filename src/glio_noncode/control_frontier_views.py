"""Stable review view over control frontier executions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_contracts import ControlFrontierEvaluation, ControlFrontierOperation, ControlFrontierRole, ControlFrontierState
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierReviewEntry:
    record_id: str
    operation: ControlFrontierOperation
    role: ControlFrontierRole
    state: ControlFrontierState
    issue_codes: tuple[str, ...]
    accepted: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierView:
    fixture_id: str
    entries: tuple[ControlFrontierReviewEntry, ...]
    state_counts: dict[str, int]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    def by_state(self, state: ControlFrontierState | str) -> tuple[ControlFrontierReviewEntry, ...]:
        selected = state.value if isinstance(state, ControlFrontierState) else str(state)
        return tuple(item for item in self.entries if item.state.value == selected)


def build_control_frontier_view(evaluation: ControlFrontierEvaluation) -> ControlFrontierView:
    entries = []
    counts: dict[str, int] = {}
    for execution in evaluation.executions:
        body = {"record_id": execution.record_id, "operation": execution.operation, "role": execution.role, "state": execution.state, "issue_codes": execution.issue_codes, "accepted": execution.accepted, "detail": str(execution.output.get("kind", "operation receipt"))}
        entries.append(ControlFrontierReviewEntry(**body, content_address=content_hash(body)))
        counts[execution.state.value] = counts.get(execution.state.value, 0) + 1
    body = {"fixture_id": evaluation.fixture_id, "entries": tuple(entries), "state_counts": dict(sorted(counts.items()))}
    return ControlFrontierView(**body, content_address=content_hash(body))


def control_frontier_review_summary(view: ControlFrontierView) -> dict[str, Any]:
    return {"fixture_id": view.fixture_id, "record_count": len(view.entries), "accepted_count": sum(item.accepted for item in view.entries), "state_counts": view.state_counts, "content_address": view.content_address}


__all__ = ["ControlFrontierReviewEntry", "ControlFrontierView", "build_control_frontier_view", "control_frontier_review_summary"]
