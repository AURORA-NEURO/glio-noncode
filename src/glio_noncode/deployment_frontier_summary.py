"""Compact summary projection for deployment frontier releases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_contracts import DeploymentFrontierEvaluation
from .deployment_frontier_metrics import DeploymentFrontierMetrics
from .deployment_frontier_release import DeploymentFrontierReleaseManifest
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierSummary:
    fixture_id: str
    release_id: str
    accepted: bool
    record_count: int
    check_count: int
    passed_checks: int
    state_counts: dict[str, int]
    issue_counts: dict[str, int]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_deployment_frontier_summary(evaluation: DeploymentFrontierEvaluation, metrics: DeploymentFrontierMetrics, release: DeploymentFrontierReleaseManifest) -> DeploymentFrontierSummary:
    body = {"fixture_id": evaluation.fixture_id, "release_id": release.release_id, "accepted": evaluation.accepted and release.accepted, "record_count": metrics.record_count, "check_count": len(evaluation.checks), "passed_checks": evaluation.passed_checks, "state_counts": metrics.state_counts, "issue_counts": metrics.issue_counts}
    return DeploymentFrontierSummary(**body, content_address=deployment_address(body))


__all__ = ["DeploymentFrontierSummary", "build_deployment_frontier_summary"]
