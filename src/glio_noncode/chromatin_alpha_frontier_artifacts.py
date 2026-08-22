"""Artifact receipts for chromatin-alpha release and review consumers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_alpha_frontier_bundle import ChromatinAlphaFrontierBundle
from .chromatin_alpha_frontier_quality_gate import ChromatinAlphaFrontierQualityReport
from .chromatin_alpha_frontier_release import ChromatinAlphaFrontierReleaseManifest
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierArtifact:
    artifact_id: str
    kind: str
    content_address: str
    media_type: str
    release_id: str

    def __post_init__(self) -> None:
        if (
            not self.artifact_id
            or not self.kind
            or not self.release_id
            or not self.content_address.startswith("sha256:")
        ):
            raise ValidationError("artifact receipt is invalid")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierArtifactInventory:
    artifacts: tuple[ChromatinAlphaFrontierArtifact, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if len(self.artifacts) < 4:
            raise ValidationError("artifact inventory requires four receipts")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def by_kind(self, kind: str) -> tuple[ChromatinAlphaFrontierArtifact, ...]:
        return tuple(artifact for artifact in self.artifacts if artifact.kind == kind)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_chromatin_alpha_frontier_artifacts(
    quality: ChromatinAlphaFrontierQualityReport,
    release: ChromatinAlphaFrontierReleaseManifest,
    bundle: ChromatinAlphaFrontierBundle,
) -> ChromatinAlphaFrontierArtifactInventory:
    artifacts = (
        ChromatinAlphaFrontierArtifact(
            "fixture",
            "fixture_manifest",
            release.artifact_addresses[0],
            "application/json",
            release.release_id,
        ),
        ChromatinAlphaFrontierArtifact(
            "quality",
            "quality_report",
            quality.content_address,
            "application/json",
            release.release_id,
        ),
        ChromatinAlphaFrontierArtifact(
            "bundle", "result_bundle", bundle.root_address, "application/json", release.release_id
        ),
        ChromatinAlphaFrontierArtifact(
            "manifest",
            "release_manifest",
            release.content_address,
            "application/json",
            release.release_id,
        ),
    )
    return ChromatinAlphaFrontierArtifactInventory(
        artifacts, quality.accepted and release.accepted and bundle.accepted
    )


__all__ = [
    "ChromatinAlphaFrontierArtifact",
    "ChromatinAlphaFrontierArtifactInventory",
    "build_chromatin_alpha_frontier_artifacts",
]
