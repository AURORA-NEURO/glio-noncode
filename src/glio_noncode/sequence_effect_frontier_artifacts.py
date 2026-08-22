"""Artifact inventory for reproducible sequence-effect releases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sequence_effect_frontier_bundle import SequenceEffectBundle
from .sequence_effect_frontier_quality_gate import SequenceEffectQualityReport
from .sequence_effect_frontier_release import SequenceEffectReleaseManifest
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceEffectArtifact:
    artifact_id: str
    artifact_kind: str
    address: str
    parent_addresses: tuple[str, ...]
    public: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceEffectArtifactInventory:
    artifacts: tuple[SequenceEffectArtifact, ...]
    root_address: str
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "artifacts": self.artifacts,
                        "root_address": self.root_address,
                        "accepted": self.accepted,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "artifact_count": len(self.artifacts),
            "root_address": self.root_address,
            "artifacts": [item.to_dict() for item in self.artifacts],
            "content_address": self.content_address,
        }


def build_sequence_effect_artifacts(
    quality: SequenceEffectQualityReport,
    release: SequenceEffectReleaseManifest,
    bundle: SequenceEffectBundle,
) -> SequenceEffectArtifactInventory:
    components = (
        SequenceEffectArtifact("fixture", "fixture", quality.evaluation.fixture_address, (), True),
        SequenceEffectArtifact(
            "evaluation",
            "evaluation",
            quality.evaluation.content_address,
            (quality.evaluation.fixture_address,),
            True,
        ),
        SequenceEffectArtifact(
            "quality",
            "quality",
            quality.content_address,
            (quality.evaluation.content_address,),
            True,
        ),
        SequenceEffectArtifact(
            "release", "release", release.content_address, (quality.content_address,), True
        ),
        SequenceEffectArtifact(
            "bundle", "bundle", bundle.content_address, (release.content_address,), True
        ),
        SequenceEffectArtifact(
            "metrics",
            "metrics",
            quality.metrics.content_address,
            (quality.evaluation.content_address,),
            True,
        ),
        SequenceEffectArtifact(
            "lineage",
            "lineage",
            quality.lineage.content_address,
            (quality.evaluation.content_address,),
            True,
        ),
        SequenceEffectArtifact(
            "policy",
            "policy",
            quality.policy.content_address,
            (quality.evaluation.content_address,),
            True,
        ),
        SequenceEffectArtifact(
            "reconciliation",
            "reconciliation",
            quality.reconciliation.content_address,
            (quality.policy.content_address,),
            True,
        ),
    )
    addresses = {item.address for item in components}
    accepted = (
        all(
            item.address.startswith("sha256:")
            and all(parent in addresses for parent in item.parent_addresses)
            for item in components
        )
        and components[0].address == quality.evaluation.fixture_address
    )
    return SequenceEffectArtifactInventory(components, release.content_address, accepted)


__all__ = [
    "SequenceEffectArtifact",
    "SequenceEffectArtifactInventory",
    "build_sequence_effect_artifacts",
]
