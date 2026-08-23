"""Release manifest construction for the deployment-governance frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_contracts import DeploymentFrontierEvaluation, DeploymentFrontierFixture
from .deployment_frontier_lineage import DeploymentFrontierLineage
from .deployment_frontier_quality_gate import DeploymentFrontierQualityReport
from .deployment_frontier_replay import DeploymentFrontierReplayReport
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierReleaseCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierReleaseManifest:
    release_id: str
    fixture_id: str
    checks: tuple[DeploymentFrontierReleaseCheck, ...]
    accepted: bool
    release_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_deployment_frontier_release(
    fixture: DeploymentFrontierFixture,
    evaluation: DeploymentFrontierEvaluation,
    quality: DeploymentFrontierQualityReport,
    lineage: DeploymentFrontierLineage,
    replay: DeploymentFrontierReplayReport,
    *,
    release_id: str = "deployment-frontier-release",
) -> DeploymentFrontierReleaseManifest:
    values = (
        ("fixture", bool(fixture.records), "fixture has records"),
        ("evaluation", evaluation.accepted, "fixture evaluation accepted"),
        ("quality", quality.accepted, "quality gate accepted"),
        ("lineage", lineage.complete, "lineage complete"),
        ("replay", replay.deterministic, "replay deterministic"),
    )
    checks = []
    for check_id, passed, detail in values:
        body = {"check_id": check_id, "passed": passed, "detail": detail}
        checks.append(DeploymentFrontierReleaseCheck(**body, content_address=deployment_address(body)))
    accepted = all(item.passed for item in checks)
    release_body = {"release_id": release_id, "fixture_id": fixture.fixture_id, "checks": tuple(checks), "accepted": accepted}
    release_address = deployment_address(release_body)
    return DeploymentFrontierReleaseManifest(**release_body, release_address=release_address, content_address=deployment_address({**release_body, "release_address": release_address}))


__all__ = ["DeploymentFrontierReleaseCheck", "DeploymentFrontierReleaseManifest", "build_deployment_frontier_release"]
