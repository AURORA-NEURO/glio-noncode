"""Final handoff bundle with safe projections only."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_artifacts import ValidationReleaseArtifactInventory
from .validation_release_frontier_package import ValidationReleasePackageManifest
from .validation_release_frontier_summary import ValidationReleaseSummary


@dataclass(frozen=True, slots=True)
class ValidationReleaseBundle:
    release_id: str
    artifact_count: int
    summary_address: str
    package_address: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def assemble_validation_release_bundle(package: ValidationReleasePackageManifest, artifacts: ValidationReleaseArtifactInventory, summary: ValidationReleaseSummary) -> ValidationReleaseBundle:
    body = {"release_id": package.release_id, "artifact_count": len(artifacts.artifacts), "summary_address": summary.content_address, "package_address": package.content_address, "accepted": package.complete and artifacts.complete and summary.accepted}
    return ValidationReleaseBundle(**body, content_address=content_hash(body))


__all__ = ["ValidationReleaseBundle", "assemble_validation_release_bundle"]
