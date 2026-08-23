"""Non-clinical claim boundary for deployment control outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_contracts import DeploymentFrontierEvaluation
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierClaimBoundaryCheck:
    check_id: str
    passed: bool
    forbidden: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierClaimBoundaryReport:
    checks: tuple[DeploymentFrontierClaimBoundaryCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_deployment_frontier_claim_boundary(evaluation: DeploymentFrontierEvaluation) -> DeploymentFrontierClaimBoundaryReport:
    serialized = str(jsonable(evaluation)).lower()
    checks = []
    for forbidden in ("clinical", "treatment decision", "diagnosis", "patient-level"):
        body = {"check_id": f"claim-boundary:{forbidden}", "passed": forbidden not in serialized, "forbidden": forbidden}
        checks.append(DeploymentFrontierClaimBoundaryCheck(**body, content_address=deployment_address(body)))
    return DeploymentFrontierClaimBoundaryReport(tuple(checks), all(item.passed for item in checks), deployment_address(tuple(checks)))


__all__ = ["DeploymentFrontierClaimBoundaryCheck", "DeploymentFrontierClaimBoundaryReport", "evaluate_deployment_frontier_claim_boundary"]
