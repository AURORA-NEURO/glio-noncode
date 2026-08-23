"""Aggregate release bundle assembly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_artifacts import DeploymentFrontierArtifactInventory
from .deployment_frontier_package import DeploymentFrontierPackageManifest
from .deployment_frontier_release import DeploymentFrontierReleaseManifest
from .deployment_frontier_summary import DeploymentFrontierSummary
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierReleaseBundle:
    bundle_id: str
    release_address: str
    package_address: str
    artifact_address: str
    summary_address: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def assemble_deployment_frontier_bundle(release: DeploymentFrontierReleaseManifest, package: DeploymentFrontierPackageManifest, artifacts: DeploymentFrontierArtifactInventory, summary: DeploymentFrontierSummary, *, bundle_id: str = "deployment-frontier-bundle") -> DeploymentFrontierReleaseBundle:
    body = {"bundle_id": bundle_id, "release_address": release.release_address, "package_address": package.content_address, "artifact_address": artifacts.content_address, "summary_address": summary.content_address, "accepted": release.accepted and package.complete and artifacts.complete and summary.accepted}
    return DeploymentFrontierReleaseBundle(**body, content_address=deployment_address(body))


__all__ = ["DeploymentFrontierReleaseBundle", "assemble_deployment_frontier_bundle"]
