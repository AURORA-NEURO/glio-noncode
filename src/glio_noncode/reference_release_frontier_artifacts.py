"""Artifact inventory and address closure for release handoff."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .reference_release_frontier_bundle import ReferenceReleaseEvidenceBundle
from .reference_release_frontier_release import ReferenceReleaseManifest
from .reference_release_frontier_runtime import ReferenceReleaseRuntimeReport
from .serialization import content_hash, jsonable


class ReferenceReleaseArtifactKind(StrEnum):
    """Named output families in the release inventory."""

    RUNTIME = "runtime"
    EVALUATION = "evaluation"
    METRICS = "metrics"
    POLICY = "policy"
    LINEAGE = "lineage"
    PROJECTION = "projection"
    RECONCILIATION = "reconciliation"
    QUALITY = "quality"
    REPLAY = "replay"
    MANIFEST = "manifest"
    BUNDLE = "bundle"


@dataclass(frozen=True, slots=True)
class ReferenceReleaseArtifact:
    """One inventory row with a type, address, and retention boundary."""

    kind: ReferenceReleaseArtifactKind
    address: str
    media_type: str
    public: bool
    retention: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceReleaseArtifactInventory:
    """Complete artifact inventory."""

    fixture_id: str
    artifacts: tuple[ReferenceReleaseArtifact, ...]
    accepted: bool
    content_address: str

    def address_map(self) -> dict[str, str]:
        return {item.kind.value: item.address for item in self.artifacts}

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "artifact_count": len(self.artifacts),
            "address_map": self.address_map(),
        }


def _artifact(
    kind: ReferenceReleaseArtifactKind, address: str, media_type: str, retention: str = "release"
) -> ReferenceReleaseArtifact:
    body = {
        "kind": kind,
        "address": address,
        "media_type": media_type,
        "public": True,
        "retention": retention,
    }
    return ReferenceReleaseArtifact(**body, content_address=content_hash(body, prefix="artifact"))


def build_reference_release_artifact_inventory(
    runtime: ReferenceReleaseRuntimeReport,
    manifest: ReferenceReleaseManifest,
    bundle: ReferenceReleaseEvidenceBundle,
) -> ReferenceReleaseArtifactInventory:
    """Index every public output produced by the package."""

    artifacts = (
        _artifact(
            ReferenceReleaseArtifactKind.RUNTIME, runtime.content_address, "application/json", "run"
        ),
        _artifact(
            ReferenceReleaseArtifactKind.EVALUATION,
            runtime.evaluation.content_address,
            "application/json",
        ),
        _artifact(
            ReferenceReleaseArtifactKind.METRICS,
            runtime.metrics.content_address,
            "application/json",
        ),
        _artifact(
            ReferenceReleaseArtifactKind.POLICY, runtime.policy.content_address, "application/json"
        ),
        _artifact(
            ReferenceReleaseArtifactKind.LINEAGE,
            runtime.lineage.content_address,
            "application/json",
        ),
        _artifact(
            ReferenceReleaseArtifactKind.PROJECTION,
            runtime.projection.content_address,
            "application/json",
        ),
        _artifact(
            ReferenceReleaseArtifactKind.RECONCILIATION,
            runtime.reconciliation.content_address,
            "application/json",
        ),
        _artifact(
            ReferenceReleaseArtifactKind.QUALITY,
            runtime.quality.content_address,
            "application/json",
        ),
        _artifact(
            ReferenceReleaseArtifactKind.REPLAY, runtime.replay.content_address, "application/json"
        ),
        _artifact(
            ReferenceReleaseArtifactKind.MANIFEST, manifest.content_address, "application/json"
        ),
        _artifact(ReferenceReleaseArtifactKind.BUNDLE, bundle.content_address, "application/json"),
    )
    accepted = len(artifacts) == len(ReferenceReleaseArtifactKind) and all(
        item.address for item in artifacts
    )
    body = {"fixture_id": runtime.fixture_id, "artifacts": artifacts, "accepted": accepted}
    return ReferenceReleaseArtifactInventory(
        **body, content_address=content_hash(body, prefix="artifact-inventory")
    )


def verify_reference_release_artifact_inventory(
    inventory: ReferenceReleaseArtifactInventory,
) -> tuple[str, ...]:
    """Return address, kind, media type, and visibility failures."""

    failures: list[str] = []
    if len(inventory.artifacts) != len(ReferenceReleaseArtifactKind):
        failures.append("artifact-count")
    if len({item.kind for item in inventory.artifacts}) != len(inventory.artifacts):
        failures.append("artifact-kind-duplicates")
    if any(not item.address for item in inventory.artifacts):
        failures.append("artifact-address-missing")
    if any(not item.media_type.startswith("application/") for item in inventory.artifacts):
        failures.append("artifact-media-type")
    if any(not item.public for item in inventory.artifacts):
        failures.append("artifact-visibility")
    if not inventory.content_address.startswith("artifact-inventory:"):
        failures.append("inventory-address")
    return tuple(failures)


__all__ = [
    "ReferenceReleaseArtifact",
    "ReferenceReleaseArtifactInventory",
    "ReferenceReleaseArtifactKind",
    "build_reference_release_artifact_inventory",
    "verify_reference_release_artifact_inventory",
]
