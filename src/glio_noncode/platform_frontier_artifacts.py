"""Artifact inventory for platform frontier release outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_contracts import PlatformFrontierFixture
from .platform_frontier_release import PlatformFrontierReleaseManifest
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierArtifact:
    artifact_id: str
    kind: str
    address: str
    required: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierArtifactInventory:
    fixture_id: str
    artifacts: tuple[PlatformFrontierArtifact, ...]
    complete: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_platform_frontier_artifact_inventory(fixture: PlatformFrontierFixture, release: PlatformFrontierReleaseManifest) -> PlatformFrontierArtifactInventory:
    specs = (("fixture", "json", fixture.content_address), ("release", "json", release.content_address), ("evaluation", "json", release.evaluation_address), ("quality", "json", release.quality_address), ("lineage", "json", release.lineage_address), ("replay", "json", release.replay_address))
    artifacts = []
    for artifact_id, kind, address in specs:
        body = {"artifact_id": artifact_id, "kind": kind, "address": address, "required": True}
        artifacts.append(PlatformFrontierArtifact(**body, content_address=content_hash(body)))
    return PlatformFrontierArtifactInventory(fixture.fixture_id, tuple(artifacts), all(item.address.startswith("sha256:") for item in artifacts), content_hash(tuple(artifacts)))


__all__ = ["PlatformFrontierArtifact", "PlatformFrontierArtifactInventory", "build_platform_frontier_artifact_inventory"]
