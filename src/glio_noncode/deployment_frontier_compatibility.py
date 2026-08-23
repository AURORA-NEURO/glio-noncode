"""Version and contract compatibility checks for deployment releases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_contracts import DEPLOYMENT_FRONTIER_VERSION
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierCompatibilityReport:
    expected_version: str
    observed_version: str
    required_runtime: str
    observed_runtime: str
    compatible: bool
    issue_codes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_deployment_frontier_compatibility(observed_version: str = DEPLOYMENT_FRONTIER_VERSION, *, observed_runtime: str = "python3.11", required_runtime: str = "python3.11") -> DeploymentFrontierCompatibilityReport:
    issues = []
    if observed_version != DEPLOYMENT_FRONTIER_VERSION:
        issues.append("contract_version_mismatch")
    if observed_runtime != required_runtime:
        issues.append("runtime_mismatch")
    body = {"expected_version": DEPLOYMENT_FRONTIER_VERSION, "observed_version": observed_version, "required_runtime": required_runtime, "observed_runtime": observed_runtime, "compatible": not issues, "issue_codes": tuple(issues)}
    return DeploymentFrontierCompatibilityReport(**body, content_address=deployment_address(body))


__all__ = ["DeploymentFrontierCompatibilityReport", "evaluate_deployment_frontier_compatibility"]
