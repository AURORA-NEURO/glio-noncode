"""Artifact inventory for methylation release and review consumers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .methylation_frontier_bundle import MethylationFrontierBundle
from .methylation_frontier_quality_gate import MethylationFrontierQualityReport
from .methylation_frontier_release import MethylationFrontierReleaseManifest
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class MethylationFrontierArtifact:
    artifact_id: str
    kind: str
    content_address: str
    media_type: str
    release_id: str

    def __post_init__(self) -> None:
        if not self.artifact_id or not self.kind or not self.content_address.startswith("sha256:"):
            raise ValidationError("artifact receipt is invalid")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MethylationFrontierArtifactInventory:
    artifacts: tuple[MethylationFrontierArtifact, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.artifacts:
            raise ValidationError("artifact inventory cannot be empty")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_methylation_frontier_artifacts(
    quality: MethylationFrontierQualityReport,
    release: MethylationFrontierReleaseManifest,
    bundle: MethylationFrontierBundle,
) -> MethylationFrontierArtifactInventory:
    artifacts = (
        MethylationFrontierArtifact(
            "fixture", "fixture", bundle.root_address, "application/json", release.release_id
        ),
        MethylationFrontierArtifact(
            "quality",
            "quality_report",
            quality.content_address,
            "application/json",
            release.release_id,
        ),
        MethylationFrontierArtifact(
            "bundle", "result_bundle", bundle.root_address, "application/json", release.release_id
        ),
        MethylationFrontierArtifact(
            "manifest",
            "release_manifest",
            release.content_address,
            "application/json",
            release.release_id,
        ),
    )
    return MethylationFrontierArtifactInventory(
        artifacts, quality.accepted and bundle.accepted and release.accepted
    )


__all__ = [
    "MethylationFrontierArtifact",
    "MethylationFrontierArtifactInventory",
    "build_methylation_frontier_artifacts",
]
