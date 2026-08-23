"""Compliance boundary checks for public aggregate deployment receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_contracts import DeploymentFrontierFixture
from .deployment_frontier_support import contains_forbidden_output, deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierComplianceCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierComplianceReport:
    checks: tuple[DeploymentFrontierComplianceCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_deployment_frontier_compliance(fixture: DeploymentFrontierFixture) -> DeploymentFrontierComplianceReport:
    serialized = fixture.to_dict()
    values = (("aggregate-only", all("patient" not in str(item.payload).lower() for item in fixture.records), True), ("https-only", all(item.uri.startswith("https://") for item in fixture.sources), True), ("secret-free", not contains_forbidden_output(serialized), True), ("source-addresses", all(item.content_address.startswith("sha256:") for item in fixture.sources), True))
    checks = []
    for check_id, observed, required in values:
        body = {"check_id": check_id, "passed": observed == required, "observed": observed, "required": required}
        checks.append(DeploymentFrontierComplianceCheck(**body, content_address=deployment_address(body)))
    return DeploymentFrontierComplianceReport(tuple(checks), all(item.passed for item in checks), deployment_address(tuple(checks)))


__all__ = ["DeploymentFrontierComplianceCheck", "DeploymentFrontierComplianceReport", "evaluate_deployment_frontier_compliance"]
