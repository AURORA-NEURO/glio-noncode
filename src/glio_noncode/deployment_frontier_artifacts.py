"""Artifact inventory and completeness checks for release receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_contracts import DeploymentFrontierFixture
from .deployment_frontier_release import DeploymentFrontierReleaseManifest
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierArtifact:
    artifact_id: str
    kind: str
    address: str
    required: bool
    present: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierArtifactInventory:
    artifacts: tuple[DeploymentFrontierArtifact, ...]
    complete: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_deployment_frontier_artifact_inventory(fixture: DeploymentFrontierFixture, release: DeploymentFrontierReleaseManifest) -> DeploymentFrontierArtifactInventory:
    rows = (
        ("fixture", "fixture", fixture.content_address, True, bool(fixture.records)),
        ("release", "release", release.release_address, True, release.accepted),
        ("manifest", "manifest", release.content_address, True, True),
    )
    artifacts = []
    for artifact_id, kind, address, required, present in rows:
        body = {"artifact_id": artifact_id, "kind": kind, "address": address, "required": required, "present": present}
        artifacts.append(DeploymentFrontierArtifact(**body, content_address=deployment_address(body)))
    return DeploymentFrontierArtifactInventory(tuple(artifacts), all(item.present for item in artifacts if item.required), deployment_address(tuple(artifacts)))


__all__ = ["DeploymentFrontierArtifact", "DeploymentFrontierArtifactInventory", "build_deployment_frontier_artifact_inventory"]
