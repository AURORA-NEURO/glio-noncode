"""Content-addressed release artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_contracts import ValidationReleaseFixture
from .validation_release_frontier_release import ValidationReleaseManifest


@dataclass(frozen=True, slots=True)
class ValidationReleaseArtifact:
    artifact_id: str
    kind: str
    content_address: str
    required: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationReleaseArtifactInventory:
    artifacts: tuple[ValidationReleaseArtifact, ...]
    complete: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_release_artifact_inventory(fixture: ValidationReleaseFixture, release: ValidationReleaseManifest) -> ValidationReleaseArtifactInventory:
    rows = (("fixture", "public-fixture", fixture.content_address, True), ("release", "release-manifest", release.content_address, True), ("schema", "input-schema", content_hash("validation-release-schema-v1"), True), ("policy", "research-policy", content_hash("validation-release-research-only-v1"), True), ("source-registry", "public-sources", content_hash(tuple(item.source_id for item in fixture.sources)), True), ("review-export", "review-table", content_hash(tuple(item.record_id for item in fixture.records)), True))
    artifacts = tuple(ValidationReleaseArtifact(*row) for row in rows)
    return ValidationReleaseArtifactInventory(artifacts, all(item.content_address.startswith("sha256:") for item in artifacts), content_hash(artifacts))


__all__ = ["ValidationReleaseArtifact", "ValidationReleaseArtifactInventory", "build_validation_release_artifact_inventory"]
