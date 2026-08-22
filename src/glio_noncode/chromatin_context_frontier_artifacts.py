"""Artifact inventory for deterministic release exports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_context_frontier_bundle import ChromatinContextFrontierBundle
from .chromatin_context_frontier_quality_gate import ChromatinContextFrontierQualityReport
from .chromatin_context_frontier_release import ChromatinContextFrontierReleaseManifest
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierArtifact:
    artifact_id: str
    path: str
    media_type: str
    content_address: str
    required: bool
    detail: str
    content_hash: str = ""

    def __post_init__(self) -> None:
        if not self.artifact_id or not self.path or not self.media_type or not self.content_address:
            raise ValidationError("artifact is incomplete")
        if not self.content_hash:
            object.__setattr__(self, "content_hash", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierArtifactInventory:
    artifacts: tuple[ChromatinContextFrontierArtifact, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.artifacts:
            raise ValidationError("artifact inventory is empty")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def required_count(self) -> int:
        return sum(item.required for item in self.artifacts)

    def by_media_type(self, media_type: str) -> tuple[ChromatinContextFrontierArtifact, ...]:
        return tuple(item for item in self.artifacts if item.media_type == media_type)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"required_count": self.required_count}


def build_chromatin_context_frontier_artifacts(
    quality: ChromatinContextFrontierQualityReport,
    release: ChromatinContextFrontierReleaseManifest,
    bundle: ChromatinContextFrontierBundle,
) -> ChromatinContextFrontierArtifactInventory:
    artifacts = (
        ChromatinContextFrontierArtifact(
            "manifest",
            "release/manifest.json",
            "application/json",
            release.content_address,
            True,
            "release manifest",
        ),
        ChromatinContextFrontierArtifact(
            "bundle",
            "release/bundle.json",
            "application/json",
            bundle.root_address,
            True,
            "bundle root and member addresses",
        ),
        ChromatinContextFrontierArtifact(
            "quality",
            "release/quality.json",
            "application/json",
            quality.content_address,
            True,
            "quality gate report",
        ),
        ChromatinContextFrontierArtifact(
            "records",
            "release/records.json",
            "application/json",
            bundle.member_addresses()["evaluation"],
            True,
            "evaluation records",
        ),
        ChromatinContextFrontierArtifact(
            "review_csv",
            "release/review.csv",
            "text/csv",
            content_hash(("review.csv", bundle.root_address)),
            True,
            "review queue export",
        ),
        ChromatinContextFrontierArtifact(
            "checks",
            "release/checks.json",
            "application/json",
            quality.content_address,
            False,
            "quality check details",
        ),
        ChromatinContextFrontierArtifact(
            "readme",
            "release/README.txt",
            "text/plain",
            content_hash(release.limitations),
            False,
            "release limitations",
        ),
    )
    return ChromatinContextFrontierArtifactInventory(
        artifacts, quality.accepted and bundle.accepted and release.accepted
    )


__all__ = [
    "ChromatinContextFrontierArtifact",
    "ChromatinContextFrontierArtifactInventory",
    "build_chromatin_context_frontier_artifacts",
]
