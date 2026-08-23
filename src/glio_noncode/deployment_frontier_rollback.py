"""Rollback planning from a deployment release manifest."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_release import DeploymentFrontierReleaseManifest
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierRollbackAction:
    action_id: str
    action: str
    prerequisite: str
    destructive: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierRollbackPlan:
    release_id: str
    prior_release_id: str
    actions: tuple[DeploymentFrontierRollbackAction, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_deployment_frontier_rollback_plan(release: DeploymentFrontierReleaseManifest, *, prior_release_id: str) -> DeploymentFrontierRollbackPlan:
    actions = []
    for sequence, (action, prerequisite) in enumerate((("freeze-new-admissions", "release-failure"), ("retain-current-receipts", "audit-log"), ("restore-prior-package", "prior-package-address"), ("replay-quality-gate", "restored-package")), start=1):
        body = {"action_id": f"rollback-{sequence}", "action": action, "prerequisite": prerequisite, "destructive": False}
        actions.append(DeploymentFrontierRollbackAction(**body, content_address=deployment_address(body)))
    return DeploymentFrontierRollbackPlan(release.release_id, prior_release_id, tuple(actions), release.accepted and bool(prior_release_id), deployment_address(tuple(actions)))


__all__ = ["DeploymentFrontierRollbackAction", "DeploymentFrontierRollbackPlan", "build_deployment_frontier_rollback_plan"]
