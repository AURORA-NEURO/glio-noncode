"""Release package manifest."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_artifacts import ValidationReleaseArtifactInventory
from .validation_release_frontier_release import ValidationReleaseManifest


@dataclass(frozen=True, slots=True)
class ValidationReleasePackageManifest:
    release_id: str
    artifact_ids: tuple[str, ...]
    complete: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_release_package_manifest(release: ValidationReleaseManifest, artifacts: ValidationReleaseArtifactInventory) -> ValidationReleasePackageManifest:
    ids = tuple(item.artifact_id for item in artifacts.artifacts)
    body = {"release_id": release.release_id, "artifact_ids": ids, "complete": release.accepted and artifacts.complete and bool(ids)}
    return ValidationReleasePackageManifest(**body, content_address=content_hash(body))


__all__ = ["ValidationReleasePackageManifest", "build_validation_release_package_manifest"]
