"""Bounded review queue projection for control frontier controls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_contracts import ControlFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierQueueItem:
    record_id: str
    priority: int
    operation: str
    state: str
    issue_codes: tuple[str, ...]
    reviewer_roles: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierReviewQueue:
    queue_id: str
    items: tuple[ControlFrontierQueueItem, ...]
    omitted_record_ids: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_control_frontier_review_queue(evaluation: ControlFrontierEvaluation, *, max_items: int = 24, queue_id: str = "control-frontier-review") -> ControlFrontierReviewQueue:
    candidates = [item for item in evaluation.executions if not item.accepted]
    ordered = sorted(candidates, key=lambda item: (-90 if item.issue_codes else -50, item.record_id))
    kept, omitted = ordered[:max_items], ordered[max_items:]
    items = []
    for execution in kept:
        body = {"record_id": execution.record_id, "priority": 90 if execution.issue_codes else 50, "operation": execution.operation.value, "state": execution.state.value, "issue_codes": execution.issue_codes, "reviewer_roles": ("platform_reviewer", "provenance_reviewer")}
        items.append(ControlFrontierQueueItem(**body, content_address=content_hash(body)))
    return ControlFrontierReviewQueue(queue_id, tuple(items), tuple(item.record_id for item in omitted), True, content_hash({"queue_id": queue_id, "items": tuple(items), "omitted_record_ids": tuple(item.record_id for item in omitted)}))


__all__ = ["ControlFrontierQueueItem", "ControlFrontierReviewQueue", "build_control_frontier_review_queue"]
