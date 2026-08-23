"""Serializable package manifest for control frontier delivery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_artifacts import ControlFrontierArtifactInventory
from .control_frontier_release import ControlFrontierReleaseManifest
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierPackageManifest:
    package_id: str
    files: tuple[str, ...]
    addresses: dict[str, str]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_control_frontier_package_manifest(inventory: ControlFrontierArtifactInventory, release: ControlFrontierReleaseManifest) -> ControlFrontierPackageManifest:
    files = tuple(f"aggregate/{item.artifact_id}.json" for item in inventory.artifacts) + ("aggregate/review.csv", "aggregate/metrics.csv", "aggregate/trace.json")
    addresses = {item.artifact_id: item.content_address for item in inventory.artifacts}
    accepted = bool(inventory.complete and release.accepted and len(files) == len(set(files)))
    body = {"package_id": "control-frontier-package", "files": files, "addresses": addresses, "accepted": accepted}
    return ControlFrontierPackageManifest(**body, content_address=content_hash(body))


__all__ = ["ControlFrontierPackageManifest", "build_control_frontier_package_manifest"]
