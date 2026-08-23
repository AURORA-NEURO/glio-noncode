"""Artifact inventory for the lifecycle beta frontier release."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .lifecycle_beta_frontier_contracts import LifecycleBetaFrontierFixture
from .lifecycle_beta_frontier_release import LifecycleBetaFrontierReleaseManifest
from .serialization import content_hash, jsonable


class LifecycleBetaFrontierArtifactKind(StrEnum):
    FIXTURE = "fixture"
    EVALUATION = "evaluation"
    QUALITY = "quality"
    LINEAGE = "lineage"
    REPLAY = "replay"
    RELEASE = "release"


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierArtifact:
    artifact_id: str
    kind: LifecycleBetaFrontierArtifactKind
    content_address: str
    required: bool
    present: bool
    content_type: str
    content_address_receipt: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierArtifactInventory:
    fixture_id: str
    artifacts: tuple[LifecycleBetaFrontierArtifact, ...]
    complete: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_lifecycle_beta_frontier_artifact_inventory(fixture: LifecycleBetaFrontierFixture, release: LifecycleBetaFrontierReleaseManifest) -> LifecycleBetaFrontierArtifactInventory:
    artifacts = []
    for kind, address in release.artifact_addresses.items():
        selected = LifecycleBetaFrontierArtifactKind(kind)
        body = {"artifact_id": f"{fixture.fixture_id}:{kind}", "kind": selected, "content_address": address, "required": True, "present": bool(address), "content_type": "application/json"}
        artifacts.append(LifecycleBetaFrontierArtifact(**body, content_address_receipt=content_hash(body)))
    body = {"fixture_id": fixture.fixture_id, "artifacts": tuple(artifacts), "complete": all(item.present for item in artifacts)}
    return LifecycleBetaFrontierArtifactInventory(**body, content_address=content_hash(body))


__all__ = ["LifecycleBetaFrontierArtifact", "LifecycleBetaFrontierArtifactInventory", "LifecycleBetaFrontierArtifactKind", "build_lifecycle_beta_frontier_artifact_inventory"]
