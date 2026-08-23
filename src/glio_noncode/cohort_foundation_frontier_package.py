"""File-level release package manifest for the C01-C04 handoff."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_artifacts import CohortFoundationArtifactInventory
from .cohort_foundation_frontier_release import CohortFoundationReleaseManifest


@dataclass(frozen=True, slots=True)
class CohortFoundationPackageFile:
    path: str
    media_type: str
    artifact_id: str
    required: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationPackageManifest:
    package_id: str
    release_id: str
    files: tuple[CohortFoundationPackageFile, ...]
    boundary: str
    ready: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_foundation_frontier_package_manifest(inventory: CohortFoundationArtifactInventory, release: CohortFoundationReleaseManifest) -> CohortFoundationPackageManifest:
    files = tuple(CohortFoundationPackageFile(f"artifacts/{artifact.artifact_id}.json", "application/json", artifact.artifact_id, True, artifact.content_address) for artifact in inventory.artifacts)
    body = {"package_id": "cohort-foundation-frontier-package", "release_id": release.release_id, "files": files, "boundary": release.public_boundary}
    return CohortFoundationPackageManifest(body["package_id"], release.release_id, files, release.public_boundary, release.ready and all(item.required for item in files), content_hash(body))


__all__ = ["CohortFoundationPackageFile", "CohortFoundationPackageManifest", "build_cohort_foundation_frontier_package_manifest"]
