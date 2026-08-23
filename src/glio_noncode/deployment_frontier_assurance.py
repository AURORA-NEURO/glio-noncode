"""Assurance summary over the deployment frontier evidence planes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_depth import DeploymentFrontierDepthAudit
from .deployment_frontier_integrity import DeploymentFrontierIntegrityReport
from .deployment_frontier_quality_gate import DeploymentFrontierQualityReport
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierAssuranceSummary:
    quality_accepted: bool
    depth_accepted: bool
    integrity_accepted: bool
    evidence_floor: int
    passed_planes: int
    total_planes: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_deployment_frontier_assurance_summary(quality: DeploymentFrontierQualityReport, depth: DeploymentFrontierDepthAudit, integrity: DeploymentFrontierIntegrityReport) -> DeploymentFrontierAssuranceSummary:
    passed = sum(item.passed for item in quality.checks) + sum(item.passed for item in depth.checks) + sum(item.passed for item in integrity.checks)
    total = len(quality.checks) + len(depth.checks) + len(integrity.checks)
    body = {"quality_accepted": quality.accepted, "depth_accepted": depth.accepted, "integrity_accepted": integrity.accepted, "evidence_floor": 80, "passed_planes": passed, "total_planes": total, "accepted": quality.accepted and depth.accepted and integrity.accepted}
    return DeploymentFrontierAssuranceSummary(**body, content_address=deployment_address(body))


__all__ = ["DeploymentFrontierAssuranceSummary", "build_deployment_frontier_assurance_summary"]
