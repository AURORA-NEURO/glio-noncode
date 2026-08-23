"""Independent release checks for deployment frontier packages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_compatibility import DeploymentFrontierCompatibilityReport
from .deployment_frontier_integrity import DeploymentFrontierIntegrityReport
from .deployment_frontier_quality_gate import DeploymentFrontierQualityReport
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierReleaseCheckReport:
    check_ids: tuple[str, ...]
    passed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_deployment_frontier_release_checks(quality: DeploymentFrontierQualityReport, integrity: DeploymentFrontierIntegrityReport, compatibility: DeploymentFrontierCompatibilityReport) -> DeploymentFrontierReleaseCheckReport:
    ids = tuple(item.check_id for item in quality.checks if not item.passed) + tuple(item.check_id for item in integrity.checks if not item.passed) + compatibility.issue_codes
    body = {"check_ids": ids, "passed": not ids}
    return DeploymentFrontierReleaseCheckReport(**body, content_address=deployment_address(body))


__all__ = ["DeploymentFrontierReleaseCheckReport", "evaluate_deployment_frontier_release_checks"]
