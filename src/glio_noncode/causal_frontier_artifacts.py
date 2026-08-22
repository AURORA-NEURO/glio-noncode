"""Artifact inventory and immutable packaging helpers."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .causal_frontier_bundle import CausalFrontierReleaseBundle
from .causal_frontier_fixture_eval import CausalFrontierEvaluation
from .causal_frontier_lineage import CausalFrontierLineageGraph
from .causal_frontier_metrics import CausalFrontierMetricsReport
from .causal_frontier_public_data import CausalFrontierFixture
from .causal_frontier_quality_gate import CausalFrontierQualityGate
from .causal_frontier_release import CausalFrontierReleaseManifest
from .serialization import content_hash, jsonable, require_non_empty


class CausalFrontierArtifactKind(StrEnum):
    FIXTURE = "fixture"
    EVALUATION = "evaluation"
    METRICS = "metrics"
    LINEAGE = "lineage"
    QUALITY = "quality"
    BUNDLE = "bundle"
    RELEASE = "release"


@dataclass(frozen=True, slots=True)
class CausalFrontierArtifact:
    artifact_id: str
    kind: CausalFrontierArtifactKind
    content_address: str
    parent_addresses: tuple[str, ...]
    byte_estimate: int
    summary: str
    content: dict[str, Any]
    inventory_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.artifact_id, "artifact_id")
        require_non_empty(self.summary, "summary")
        if self.byte_estimate < 0:
            raise ValueError("byte estimate must be nonnegative")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalFrontierArtifactInventory:
    artifacts: tuple[CausalFrontierArtifact, ...]
    root_artifact_id: str
    content_address: str

    def __post_init__(self) -> None:
        if self.root_artifact_id not in {item.artifact_id for item in self.artifacts}:
            raise ValueError("root artifact must be in inventory")

    def by_kind(self, kind: CausalFrontierArtifactKind) -> tuple[CausalFrontierArtifact, ...]:
        return tuple(item for item in self.artifacts if item.kind is kind)

    def by_id(self, artifact_id: str) -> CausalFrontierArtifact:
        return next(item for item in self.artifacts if item.artifact_id == artifact_id)

    @property
    def total_bytes(self) -> int:
        return sum(item.byte_estimate for item in self.artifacts)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"total_bytes": self.total_bytes}


def _artifact(
    artifact_id: str,
    kind: CausalFrontierArtifactKind,
    content: Any,
    parent_addresses: Iterable[str],
    summary: str,
) -> CausalFrontierArtifact:
    content_dict = jsonable(content)
    content_address = content.content_address if hasattr(content, "content_address") else content_hash(content_dict)
    parents = tuple(sorted(set(parent_addresses)))
    body = {
        "artifact_id": artifact_id,
        "kind": kind,
        "content_address": content_address,
        "parent_addresses": parents,
        "byte_estimate": len(str(content_dict).encode("utf-8")),
        "summary": summary,
        "content": content_dict,
    }
    return CausalFrontierArtifact(**body, inventory_address=content_hash(body))


def build_causal_frontier_artifact_inventory(
    fixture: CausalFrontierFixture,
    evaluation: CausalFrontierEvaluation,
    metrics: CausalFrontierMetricsReport,
    lineage: CausalFrontierLineageGraph,
    quality: CausalFrontierQualityGate,
    bundle: CausalFrontierReleaseBundle,
    release: CausalFrontierReleaseManifest,
) -> CausalFrontierArtifactInventory:
    fixture_artifact = _artifact("artifact-fixture", CausalFrontierArtifactKind.FIXTURE, fixture, (), "public aggregate fixture")
    evaluation_artifact = _artifact("artifact-evaluation", CausalFrontierArtifactKind.EVALUATION, evaluation, (fixture.content_address,), "positive and control replay")
    metrics_artifact = _artifact("artifact-metrics", CausalFrontierArtifactKind.METRICS, metrics, (evaluation.content_address,), "bounded operation metrics")
    lineage_artifact = _artifact("artifact-lineage", CausalFrontierArtifactKind.LINEAGE, lineage, (fixture.content_address, evaluation.content_address), "source and transform lineage")
    quality_artifact = _artifact("artifact-quality", CausalFrontierArtifactKind.QUALITY, quality, (evaluation.content_address, lineage.content_address), "blocking quality checks")
    bundle_artifact = _artifact("artifact-bundle", CausalFrontierArtifactKind.BUNDLE, bundle, (fixture.content_address, evaluation.content_address, metrics.content_address, lineage.content_address, quality.content_address), "release bundle")
    release_artifact = _artifact("artifact-release", CausalFrontierArtifactKind.RELEASE, release, (bundle.content_address, quality.content_address), "release manifest")
    artifacts = (fixture_artifact, evaluation_artifact, metrics_artifact, lineage_artifact, quality_artifact, bundle_artifact, release_artifact)
    body = {"artifacts": artifacts, "root_artifact_id": release_artifact.artifact_id}
    return CausalFrontierArtifactInventory(**body, content_address=content_hash(body))


__all__ = [
    "CausalFrontierArtifact",
    "CausalFrontierArtifactInventory",
    "CausalFrontierArtifactKind",
    "build_causal_frontier_artifact_inventory",
]
