"""Reproducible handoff packet for a deployment frontier run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_contracts import DeploymentFrontierEvaluation, DeploymentFrontierFixture
from .deployment_frontier_metrics import DeploymentFrontierMetrics
from .deployment_frontier_review_queue import DeploymentFrontierReviewQueue
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierHandoffItem:
    item_id: str
    kind: str
    address: str
    required: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierHandoff:
    fixture_id: str
    items: tuple[DeploymentFrontierHandoffItem, ...]
    open_review_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_deployment_frontier_handoff(fixture: DeploymentFrontierFixture, evaluation: DeploymentFrontierEvaluation, metrics: DeploymentFrontierMetrics, queue: DeploymentFrontierReviewQueue) -> DeploymentFrontierHandoff:
    rows = (("fixture", "fixture", fixture.content_address, True), ("evaluation", "evaluation", evaluation.content_address, True), ("metrics", "metrics", metrics.content_address, True), ("review-queue", "review", queue.content_address, True))
    items = []
    for item_id, kind, address, required in rows:
        body = {"item_id": item_id, "kind": kind, "address": address, "required": required}
        items.append(DeploymentFrontierHandoffItem(**body, content_address=deployment_address(body)))
    return DeploymentFrontierHandoff(fixture.fixture_id, tuple(items), len(queue.items), all(item.address.startswith("sha256:") for item in items), deployment_address(tuple(items)))


__all__ = ["DeploymentFrontierHandoff", "DeploymentFrontierHandoffItem", "build_deployment_frontier_handoff"]
