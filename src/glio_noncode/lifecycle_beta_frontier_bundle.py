"""Release bundle assembly for the lifecycle beta frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_artifacts import LifecycleBetaFrontierArtifactInventory
from .lifecycle_beta_frontier_handoff import LifecycleBetaFrontierHandoff
from .lifecycle_beta_frontier_quality_gate import LifecycleBetaFrontierQualityReport
from .lifecycle_beta_frontier_release import LifecycleBetaFrontierReleaseManifest
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierReleaseBundle:
    bundle_id: str
    release: LifecycleBetaFrontierReleaseManifest
    artifacts: LifecycleBetaFrontierArtifactInventory
    handoff: LifecycleBetaFrontierHandoff
    quality: LifecycleBetaFrontierQualityReport
    publishable: bool
    required_review: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def assemble_lifecycle_beta_frontier_bundle(bundle_id: str, release: LifecycleBetaFrontierReleaseManifest, artifacts: LifecycleBetaFrontierArtifactInventory, handoff: LifecycleBetaFrontierHandoff, quality: LifecycleBetaFrontierQualityReport) -> LifecycleBetaFrontierReleaseBundle:
    required = []
    if not release.accepted:
        required.append("release_manifest")
    if not artifacts.complete:
        required.append("artifact_inventory")
    if not handoff.accepted:
        required.append("handoff")
    if not quality.accepted:
        required.append("quality_gate")
    body = {"bundle_id": bundle_id, "release": release, "artifacts": artifacts, "handoff": handoff, "quality": quality, "publishable": not required, "required_review": tuple(required)}
    return LifecycleBetaFrontierReleaseBundle(**body, content_address=content_hash(body))


__all__ = ["LifecycleBetaFrontierReleaseBundle", "assemble_lifecycle_beta_frontier_bundle"]
