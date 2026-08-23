"""Artifact inventory for the control frontier release."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_contracts import ControlFrontierFixture
from .control_frontier_release import ControlFrontierReleaseManifest
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierArtifact:
    artifact_id: str
    kind: str
    content_address: str
    required: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierArtifactInventory:
    fixture_id: str
    artifacts: tuple[ControlFrontierArtifact, ...]
    complete: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_control_frontier_artifact_inventory(fixture: ControlFrontierFixture, release: ControlFrontierReleaseManifest) -> ControlFrontierArtifactInventory:
    values = (("fixture", "aggregate_fixture", fixture.content_address), *tuple((key, "release_receipt", value) for key, value in release.artifact_addresses.items() if key != "fixture"))
    artifacts = tuple(ControlFrontierArtifact(artifact_id, kind, address, True) for artifact_id, kind, address in values)
    complete = bool(release.accepted and all(item.content_address.startswith("sha256:") for item in artifacts))
    return ControlFrontierArtifactInventory(fixture.fixture_id, artifacts, complete, content_hash({"fixture_id": fixture.fixture_id, "artifacts": artifacts, "complete": complete}))


__all__ = ["ControlFrontierArtifact", "ControlFrontierArtifactInventory", "build_control_frontier_artifact_inventory"]
