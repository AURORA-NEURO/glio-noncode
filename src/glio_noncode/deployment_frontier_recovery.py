"""Recovery actions for denied or held deployment operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_contracts import DeploymentFrontierEvaluation
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierRecoveryAction:
    record_id: str
    issue_code: str
    action: str
    retryable: bool
    requires_review: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierRecoveryPlan:
    actions: tuple[DeploymentFrontierRecoveryAction, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_deployment_frontier_recovery_plan(evaluation: DeploymentFrontierEvaluation) -> DeploymentFrontierRecoveryPlan:
    actions = []
    for execution in evaluation.executions:
        for issue in execution.issue_codes:
            retryable = issue in {"invalid_digest", "bundle_requirements_missing", "site_unavailable"}
            body = {"record_id": execution.record_id, "issue_code": issue, "action": "repair_and_replay" if retryable else "review_and_hold", "retryable": retryable, "requires_review": True}
            actions.append(DeploymentFrontierRecoveryAction(**body, content_address=deployment_address(body)))
    return DeploymentFrontierRecoveryPlan(tuple(actions), all(item.requires_review for item in actions), deployment_address(tuple(actions)))


__all__ = ["DeploymentFrontierRecoveryAction", "DeploymentFrontierRecoveryPlan", "build_deployment_frontier_recovery_plan"]
