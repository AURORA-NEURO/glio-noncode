"""Bounded review queue derived from control outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_contracts import DeploymentFrontierEvaluation
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierQueueItem:
    queue_id: str
    record_id: str
    operation: str
    priority: int
    issue_codes: tuple[str, ...]
    reviewer_scope: str
    status: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierReviewQueue:
    items: tuple[DeploymentFrontierQueueItem, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_deployment_frontier_review_queue(evaluation: DeploymentFrontierEvaluation) -> DeploymentFrontierReviewQueue:
    items = []
    for sequence, execution in enumerate((item for item in evaluation.executions if item.issue_codes), start=1):
        scope = {"privacy_security_policy": "privacy-review", "local_deployment_bundle": "release-operations", "federated_execution": "federation-review", "release_rollback": "release-operations"}[execution.operation.value]
        body = {"queue_id": f"deployment-review-{sequence:03d}", "record_id": execution.record_id, "operation": execution.operation.value, "priority": 100 if "failed_check" in str(execution.issue_codes) else 80, "issue_codes": execution.issue_codes, "reviewer_scope": scope, "status": "open"}
        items.append(DeploymentFrontierQueueItem(**body, content_address=deployment_address(body)))
    ordered = tuple(sorted(items, key=lambda item: (-item.priority, item.queue_id)))
    return DeploymentFrontierReviewQueue(ordered, len(ordered) == 12, deployment_address(ordered))


def filter_deployment_frontier_review_queue(queue: DeploymentFrontierReviewQueue, status: str = "open") -> tuple[DeploymentFrontierQueueItem, ...]:
    return tuple(item for item in queue.items if item.status == status)


__all__ = ["DeploymentFrontierQueueItem", "DeploymentFrontierReviewQueue", "build_deployment_frontier_review_queue", "filter_deployment_frontier_review_queue"]
