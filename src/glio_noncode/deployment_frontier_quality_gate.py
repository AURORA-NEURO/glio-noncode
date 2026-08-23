"""Blocking quality gate for deployment-governance evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_adapters import DeploymentFrontierAdapterRegistry
from .deployment_frontier_contracts import DeploymentFrontierEvaluation
from .deployment_frontier_public_data import DeploymentFrontierDataAudit
from .deployment_frontier_reconciliation import DeploymentFrontierReconciliation
from .deployment_frontier_schema import DeploymentFrontierSchema
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierQualityCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierQualityReport:
    checks: tuple[DeploymentFrontierQualityCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def run_deployment_frontier_quality_gate(
    audit: DeploymentFrontierDataAudit,
    evaluation: DeploymentFrontierEvaluation,
    adapters: DeploymentFrontierAdapterRegistry,
    schema: DeploymentFrontierSchema,
    reconciliation: DeploymentFrontierReconciliation,
) -> DeploymentFrontierQualityReport:
    values = (
        ("data-audit", audit.accepted, True, "public data boundary"),
        ("fixture-evaluation", evaluation.accepted, True, "all positive and control checks"),
        ("check-floor", len(evaluation.checks), 80, "five checks for each of sixteen records"),
        ("adapter-count", len(adapters.specs), 4, "one adapter per operation"),
        ("schema-fields", len(schema.fields), 14, "required operation fields"),
        ("reconciliation", reconciliation.accepted, True, "expected states match observed states"),
    )
    checks = []
    for check_id, observed, required, detail in values:
        body = {"check_id": check_id, "passed": observed == required, "observed": observed, "required": required, "detail": detail}
        checks.append(DeploymentFrontierQualityCheck(**body, content_address=deployment_address(body)))
    return DeploymentFrontierQualityReport(tuple(checks), all(item.passed for item in checks), deployment_address(tuple(checks)))


__all__ = ["DeploymentFrontierQualityCheck", "DeploymentFrontierQualityReport", "run_deployment_frontier_quality_gate"]
