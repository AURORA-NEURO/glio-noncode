"""Artifact inventory for Domain 08 release consumers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_frontier_bundle import CellContextFrontierBundle
from .cell_context_frontier_quality_gate import CellContextFrontierQualityReport
from .cell_context_frontier_release import CellContextFrontierReleaseManifest
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextFrontierArtifact:
    artifact_id: str
    path: str
    media_type: str
    content_address: str
    required: bool
    detail: str
    content_hash: str = ""

    def __post_init__(self) -> None:
        if not self.artifact_id or not self.path or not self.media_type or not self.content_address:
            raise ValidationError("cell artifact is incomplete")
        if not self.content_hash:
            object.__setattr__(self, "content_hash", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextFrontierArtifactInventory:
    artifacts: tuple[CellContextFrontierArtifact, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.artifacts:
            raise ValidationError("cell artifact inventory is empty")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def required_count(self) -> int:
        return sum(item.required for item in self.artifacts)

    def by_media_type(self, media_type: str) -> tuple[CellContextFrontierArtifact, ...]:
        return tuple(item for item in self.artifacts if item.media_type == media_type)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"required_count": self.required_count}


def build_cell_context_frontier_artifacts(
    quality: CellContextFrontierQualityReport,
    release: CellContextFrontierReleaseManifest,
    bundle: CellContextFrontierBundle,
) -> CellContextFrontierArtifactInventory:
    artifacts = (
        CellContextFrontierArtifact(
            "manifest",
            "release/manifest.json",
            "application/json",
            release.content_address,
            True,
            "release manifest",
        ),
        CellContextFrontierArtifact(
            "bundle",
            "release/bundle.json",
            "application/json",
            bundle.root_address,
            True,
            "bundle root",
        ),
        CellContextFrontierArtifact(
            "quality",
            "release/quality.json",
            "application/json",
            quality.content_address,
            True,
            "quality gate",
        ),
        CellContextFrontierArtifact(
            "evaluation",
            "release/evaluation.json",
            "application/json",
            bundle.member("evaluation").content_address,
            True,
            "operation results",
        ),
        CellContextFrontierArtifact(
            "review_csv",
            "release/review.csv",
            "text/csv",
            content_hash(("review", bundle.root_address)),
            True,
            "review projection",
        ),
        CellContextFrontierArtifact(
            "limitations",
            "release/limitations.json",
            "application/json",
            content_hash(release.limitations),
            False,
            "open evidence limits",
        ),
        CellContextFrontierArtifact(
            "checks",
            "release/checks.json",
            "application/json",
            quality.content_address,
            False,
            "quality check details",
        ),
    )
    accepted = quality.accepted and release.accepted and bundle.accepted
    return CellContextFrontierArtifactInventory(artifacts, accepted)


__all__ = [
    "CellContextFrontierArtifact",
    "CellContextFrontierArtifactInventory",
    "build_cell_context_frontier_artifacts",
]
