"""Operational response matrix for deployment control outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_contracts import DeploymentFrontierEvaluation, DeploymentFrontierOperation
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierOperationalRow:
    operation: DeploymentFrontierOperation
    observed_states: tuple[str, ...]
    required_action: str
    severity: str
    owner_scope: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierOperationalMatrix:
    rows: tuple[DeploymentFrontierOperationalRow, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_deployment_frontier_operational_matrix(evaluation: DeploymentFrontierEvaluation) -> DeploymentFrontierOperationalMatrix:
    actions = {
        DeploymentFrontierOperation.PRIVACY_SECURITY_POLICY: ("review_denied_access", "high", "privacy-review"),
        DeploymentFrontierOperation.LOCAL_DEPLOYMENT_BUNDLE: ("hold_bundle_and_repair_manifest", "high", "release-operations"),
        DeploymentFrontierOperation.FEDERATED_EXECUTION: ("retain_site_local_hold", "high", "federation-review"),
        DeploymentFrontierOperation.RELEASE_ROLLBACK: ("block_transition_and_review", "critical", "release-operations"),
    }
    rows = []
    for operation in DeploymentFrontierOperation:
        selected = tuple(item for item in evaluation.executions if item.operation is operation)
        action, severity, owner = actions[operation]
        body = {"operation": operation, "observed_states": tuple(item.state.value for item in selected), "required_action": action, "severity": severity, "owner_scope": owner, "accepted": len(selected) == 4}
        rows.append(DeploymentFrontierOperationalRow(**body, content_address=deployment_address(body)))
    return DeploymentFrontierOperationalMatrix(tuple(rows), all(item.accepted for item in rows), deployment_address(tuple(rows)))


__all__ = ["DeploymentFrontierOperationalMatrix", "DeploymentFrontierOperationalRow", "build_deployment_frontier_operational_matrix"]
