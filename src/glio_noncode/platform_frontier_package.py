"""Package manifest for a platform frontier release."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_artifacts import PlatformFrontierArtifactInventory
from .platform_frontier_release import PlatformFrontierReleaseManifest
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierPackageManifest:
    package_id: str
    release_id: str
    artifact_ids: tuple[str, ...]
    media_types: dict[str, str]
    complete: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_platform_frontier_package_manifest(release: PlatformFrontierReleaseManifest, inventory: PlatformFrontierArtifactInventory) -> PlatformFrontierPackageManifest:
    body = {"package_id": f"package:{release.release_id}", "release_id": release.release_id, "artifact_ids": tuple(item.artifact_id for item in inventory.artifacts), "media_types": {item.artifact_id: "application/json" for item in inventory.artifacts}, "complete": inventory.complete and release.accepted}
    return PlatformFrontierPackageManifest(**body, content_address=content_hash(body))


__all__ = ["PlatformFrontierPackageManifest", "build_platform_frontier_package_manifest"]
