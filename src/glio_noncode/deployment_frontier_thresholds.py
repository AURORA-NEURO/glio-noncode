"""Threshold probes for privacy, bundle, federation, and release gates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_contracts import DeploymentFrontierOperation
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierThresholdProbe:
    probe_id: str
    operation: DeploymentFrontierOperation
    boundary: str
    lower_case: str
    upper_case: str
    expected_direction: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierThresholdReport:
    probes: tuple[DeploymentFrontierThresholdProbe, ...]
    accepted: bool
    content_address: str

    @property
    def probe_count(self) -> int:
        return len(self.probes)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_deployment_frontier_threshold_report() -> DeploymentFrontierThresholdReport:
    rows = (
        (DeploymentFrontierOperation.PRIVACY_SECURITY_POLICY, "role intersection", "role present", "role absent", "present_allows_absent_denies"),
        (DeploymentFrontierOperation.LOCAL_DEPLOYMENT_BUNDLE, "digest prefix", "sha256 digest", "malformed digest", "valid_ready_invalid_hold"),
        (DeploymentFrontierOperation.FEDERATED_EXECUTION, "privacy budget", "cost within budget", "cost over budget", "within_ready_over_hold"),
        (DeploymentFrontierOperation.RELEASE_ROLLBACK, "required gates", "all true", "one false", "all_release_one_denied"),
    )
    probes = []
    for sequence, (operation, boundary, lower_case, upper_case, direction) in enumerate(rows, start=1):
        body = {"probe_id": f"threshold-{sequence}", "operation": operation, "boundary": boundary, "lower_case": lower_case, "upper_case": upper_case, "expected_direction": direction}
        probes.append(DeploymentFrontierThresholdProbe(**body, content_address=deployment_address(body)))
    return DeploymentFrontierThresholdReport(tuple(probes), len(probes) == 4, deployment_address(tuple(probes)))


def validate_deployment_frontier_threshold_report(report: DeploymentFrontierThresholdReport) -> tuple[str, ...]:
    return () if report.accepted and report.probe_count == 4 else ("threshold_floor",)


__all__ = ["DeploymentFrontierThresholdProbe", "DeploymentFrontierThresholdReport", "build_deployment_frontier_threshold_report", "validate_deployment_frontier_threshold_report"]
