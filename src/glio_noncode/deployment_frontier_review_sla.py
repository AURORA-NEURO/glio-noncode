"""Review response bands for deployment control queues."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_review_queue import DeploymentFrontierReviewQueue
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierReviewSlaRow:
    queue_id: str
    priority: int
    response_hours: int
    escalation: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierReviewSla:
    rows: tuple[DeploymentFrontierReviewSlaRow, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_deployment_frontier_review_sla(queue: DeploymentFrontierReviewQueue) -> DeploymentFrontierReviewSla:
    rows = []
    for item in queue.items:
        hours = 4 if item.priority >= 100 else 24
        body = {"queue_id": item.queue_id, "priority": item.priority, "response_hours": hours, "escalation": "release-owner" if item.priority >= 100 else "domain-review"}
        rows.append(DeploymentFrontierReviewSlaRow(**body, content_address=deployment_address(body)))
    return DeploymentFrontierReviewSla(tuple(rows), all(item.response_hours > 0 for item in rows), deployment_address(tuple(rows)))


__all__ = ["DeploymentFrontierReviewSla", "DeploymentFrontierReviewSlaRow", "build_deployment_frontier_review_sla"]
