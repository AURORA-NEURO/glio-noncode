"""Diagnostic findings derived from deployment frontier evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_contracts import DeploymentFrontierEvaluation
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierDiagnostic:
    finding_id: str
    severity: str
    record_id: str | None
    code: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierDiagnostics:
    findings: tuple[DeploymentFrontierDiagnostic, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def diagnose_deployment_frontier(evaluation: DeploymentFrontierEvaluation) -> DeploymentFrontierDiagnostics:
    findings = []
    for execution in evaluation.executions:
        for issue in execution.issue_codes:
            body = {"finding_id": f"{execution.record_id}:{issue}", "severity": "blocking" if execution.role.value == "control" else "review", "record_id": execution.record_id, "code": issue, "detail": f"declared control boundary: {issue}"}
            findings.append(DeploymentFrontierDiagnostic(**body, content_address=deployment_address(body)))
    return DeploymentFrontierDiagnostics(tuple(findings), all(item.severity in {"blocking", "review"} for item in findings), deployment_address(tuple(findings)))


__all__ = ["DeploymentFrontierDiagnostic", "DeploymentFrontierDiagnostics", "diagnose_deployment_frontier"]
