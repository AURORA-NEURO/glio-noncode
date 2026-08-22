"""Artifact inventory for release and review consumers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_regulation_frontier_bundle import SequenceRegulationBundle
from .sequence_regulation_frontier_quality_gate import SequenceRegulationQualityReport
from .sequence_regulation_frontier_release import SequenceRegulationReleaseManifest
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceRegulationArtifact:
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
class SequenceRegulationArtifactInventory:
    artifacts: tuple[SequenceRegulationArtifact, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.artifacts:
            raise ValidationError("artifact inventory cannot be empty")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_sequence_regulation_artifacts(
    quality: SequenceRegulationQualityReport,
    release: SequenceRegulationReleaseManifest,
    bundle: SequenceRegulationBundle,
) -> SequenceRegulationArtifactInventory:
    artifacts = (
        SequenceRegulationArtifact(
            "fixture", "fixture", bundle.root_address, "application/json", release.release_id
        ),
        SequenceRegulationArtifact(
            "quality",
            "quality_report",
            quality.content_address,
            "application/json",
            release.release_id,
        ),
        SequenceRegulationArtifact(
            "bundle", "result_bundle", bundle.root_address, "application/json", release.release_id
        ),
        SequenceRegulationArtifact(
            "manifest",
            "release_manifest",
            release.content_address,
            "application/json",
            release.release_id,
        ),
    )
    return SequenceRegulationArtifactInventory(
        artifacts, quality.accepted and bundle.accepted and release.accepted
    )


__all__ = [
    "SequenceRegulationArtifact",
    "SequenceRegulationArtifactInventory",
    "build_sequence_regulation_artifacts",
]
