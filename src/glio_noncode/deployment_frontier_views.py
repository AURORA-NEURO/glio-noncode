"""Stable review projection for deployment frontier rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_contracts import DeploymentFrontierEvaluation
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierReviewEntry:
    record_id: str
    operation: str
    role: str
    state: str
    issue_codes: tuple[str, ...]
    review_required: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierView:
    entries: tuple[DeploymentFrontierReviewEntry, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_deployment_frontier_view(evaluation: DeploymentFrontierEvaluation) -> DeploymentFrontierView:
    entries = []
    for item in evaluation.executions:
        body = {"record_id": item.record_id, "operation": item.operation.value, "role": item.role.value, "state": item.state.value, "issue_codes": item.issue_codes, "review_required": bool(item.issue_codes)}
        entries.append(DeploymentFrontierReviewEntry(**body, content_address=deployment_address(body)))
    return DeploymentFrontierView(tuple(entries), deployment_address(tuple(entries)))


def deployment_frontier_review_summary(view: DeploymentFrontierView) -> dict[str, Any]:
    return {"entry_count": len(view.entries), "review_count": sum(item.review_required for item in view.entries), "content_address": view.content_address}


__all__ = ["DeploymentFrontierReviewEntry", "DeploymentFrontierView", "build_deployment_frontier_view", "deployment_frontier_review_summary"]
