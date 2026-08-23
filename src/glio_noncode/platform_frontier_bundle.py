"""Combined platform evidence bundle projection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_artifacts import PlatformFrontierArtifactInventory
from .platform_frontier_package import PlatformFrontierPackageManifest
from .platform_frontier_release import PlatformFrontierReleaseManifest
from .platform_frontier_summary import PlatformFrontierSummary
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierReleaseBundle:
    release: PlatformFrontierReleaseManifest
    package: PlatformFrontierPackageManifest
    artifacts: PlatformFrontierArtifactInventory
    summary: PlatformFrontierSummary
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def assemble_platform_frontier_bundle(release: PlatformFrontierReleaseManifest, package: PlatformFrontierPackageManifest, artifacts: PlatformFrontierArtifactInventory, summary: PlatformFrontierSummary) -> PlatformFrontierReleaseBundle:
    body = {"release": release, "package": package, "artifacts": artifacts, "summary": summary, "accepted": release.accepted and package.complete and artifacts.complete and summary.release_accepted}
    return PlatformFrontierReleaseBundle(**body, content_address=content_hash(body))


__all__ = ["PlatformFrontierReleaseBundle", "assemble_platform_frontier_bundle"]
