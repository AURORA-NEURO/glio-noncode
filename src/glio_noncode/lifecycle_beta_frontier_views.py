"""Stable review views over beta-frontier executions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_contracts import LifecycleBetaFrontierEvaluation, LifecycleBetaFrontierOperation, LifecycleBetaFrontierRole, LifecycleBetaFrontierState
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierReviewEntry:
    record_id: str
    operation: LifecycleBetaFrontierOperation
    role: LifecycleBetaFrontierRole
    state: LifecycleBetaFrontierState
    issue_codes: tuple[str, ...]
    accepted: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierView:
    fixture_id: str
    entries: tuple[LifecycleBetaFrontierReviewEntry, ...]
    state_counts: dict[str, int]
    content_address: str

    def by_state(self, state: LifecycleBetaFrontierState | str) -> tuple[LifecycleBetaFrontierReviewEntry, ...]:
        selected = state.value if isinstance(state, LifecycleBetaFrontierState) else str(state)
        return tuple(item for item in self.entries if item.state.value == selected)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_lifecycle_beta_frontier_view(evaluation: LifecycleBetaFrontierEvaluation) -> LifecycleBetaFrontierView:
    entries = []
    counts: dict[str, int] = {}
    for item in evaluation.executions:
        entry_body = {"record_id": item.record_id, "operation": item.operation, "role": item.role, "state": item.state, "issue_codes": item.issue_codes, "accepted": item.accepted, "detail": str(item.output.get("detail", ""))}
        entries.append(LifecycleBetaFrontierReviewEntry(**entry_body, content_address=content_hash(entry_body)))
        counts[item.state.value] = counts.get(item.state.value, 0) + 1
    body = {"fixture_id": evaluation.fixture_id, "entries": tuple(entries), "state_counts": dict(sorted(counts.items()))}
    return LifecycleBetaFrontierView(**body, content_address=content_hash(body))


def lifecycle_beta_frontier_review_summary(view: LifecycleBetaFrontierView) -> dict[str, Any]:
    return {"fixture_id": view.fixture_id, "record_count": len(view.entries), "state_counts": view.state_counts, "accepted_count": sum(item.accepted for item in view.entries), "content_address": view.content_address}


def filter_lifecycle_beta_frontier_review_queue(view: LifecycleBetaFrontierView, *, operation: LifecycleBetaFrontierOperation | str | None = None, state: LifecycleBetaFrontierState | str | None = None, include_controls: bool = True) -> tuple[LifecycleBetaFrontierReviewEntry, ...]:
    selected_operation = None if operation is None else operation.value if isinstance(operation, LifecycleBetaFrontierOperation) else str(operation)
    selected_state = None if state is None else state.value if isinstance(state, LifecycleBetaFrontierState) else str(state)
    return tuple(item for item in view.entries if (selected_operation is None or item.operation.value == selected_operation) and (selected_state is None or item.state.value == selected_state) and (include_controls or item.role is LifecycleBetaFrontierRole.POSITIVE))


__all__ = ["LifecycleBetaFrontierReviewEntry", "LifecycleBetaFrontierView", "build_lifecycle_beta_frontier_view", "filter_lifecycle_beta_frontier_review_queue", "lifecycle_beta_frontier_review_summary"]
