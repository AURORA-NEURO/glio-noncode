"""Package manifest for deployment frontier artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_artifacts import DeploymentFrontierArtifactInventory
from .deployment_frontier_release import DeploymentFrontierReleaseManifest
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierPackageFile:
    file_id: str
    kind: str
    address: str
    required: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierPackageManifest:
    package_id: str
    files: tuple[DeploymentFrontierPackageFile, ...]
    complete: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_deployment_frontier_package_manifest(release: DeploymentFrontierReleaseManifest, artifacts: DeploymentFrontierArtifactInventory, *, package_id: str = "deployment-frontier-package") -> DeploymentFrontierPackageManifest:
    files = []
    for artifact in artifacts.artifacts:
        body = {"file_id": artifact.artifact_id, "kind": artifact.kind, "address": artifact.address, "required": artifact.required}
        files.append(DeploymentFrontierPackageFile(**body, content_address=deployment_address(body)))
    return DeploymentFrontierPackageManifest(package_id, tuple(files), release.accepted and artifacts.complete and all(item.address.startswith("sha256:") for item in files), deployment_address(tuple(files)))


__all__ = ["DeploymentFrontierPackageFile", "DeploymentFrontierPackageManifest", "build_deployment_frontier_package_manifest"]
