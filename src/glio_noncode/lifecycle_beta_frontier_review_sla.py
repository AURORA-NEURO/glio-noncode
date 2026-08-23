"""Review queue service-level targets without claiming staffing completion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_review_queue import LifecycleBetaFrontierReviewQueue
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierReviewSlaRow:
    record_id: str
    priority: float
    target_hours: int
    escalation: str
    assigned_roles: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierReviewSla:
    rows: tuple[LifecycleBetaFrontierReviewSlaRow, ...]
    unassigned_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_lifecycle_beta_frontier_review_sla(queue: LifecycleBetaFrontierReviewQueue) -> LifecycleBetaFrontierReviewSla:
    rows = []
    for item in queue.items:
        target = 4 if item.priority >= 0.95 else 24 if item.priority >= 0.8 else 72
        body = {"record_id": item.record_id, "priority": item.priority, "target_hours": target, "escalation": "same_day" if target <= 4 else "standard", "assigned_roles": item.required_roles}
        rows.append(LifecycleBetaFrontierReviewSlaRow(**body, content_address=content_hash(body)))
    return LifecycleBetaFrontierReviewSla(tuple(rows), len(queue.omitted_record_ids), content_hash({"rows": tuple(rows), "omitted": queue.omitted_record_ids}))


__all__ = ["LifecycleBetaFrontierReviewSla", "LifecycleBetaFrontierReviewSlaRow", "build_lifecycle_beta_frontier_review_sla"]
