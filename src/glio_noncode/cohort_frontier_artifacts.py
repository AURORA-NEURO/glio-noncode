"""Seven-node artifact inventory for cohort convergence releases."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .cohort_frontier_bundle import CohortFrontierReleaseBundle
from .cohort_frontier_fixture_eval import CohortFrontierEvaluation
from .cohort_frontier_lineage import CohortFrontierLineageGraph
from .cohort_frontier_metrics import CohortFrontierMetricsReport
from .cohort_frontier_public_data import CohortFrontierFixture
from .cohort_frontier_quality_gate import CohortFrontierQualityGate
from .cohort_frontier_release import CohortFrontierReleaseManifest
from .serialization import content_hash, jsonable, require_non_empty


class CohortFrontierArtifactKind(StrEnum):
    FIXTURE = "fixture"
    EVALUATION = "evaluation"
    METRICS = "metrics"
    LINEAGE = "lineage"
    QUALITY = "quality"
    BUNDLE = "bundle"
    RELEASE = "release"


@dataclass(frozen=True, slots=True)
class CohortFrontierArtifact:
    artifact_id: str
    kind: CohortFrontierArtifactKind
    content_address: str
    parent_addresses: tuple[str, ...]
    byte_estimate: int
    summary: str
    content: dict[str, Any]
    inventory_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.artifact_id, "artifact_id")
        require_non_empty(self.summary, "summary")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFrontierArtifactInventory:
    artifacts: tuple[CohortFrontierArtifact, ...]
    root_artifact_id: str
    content_address: str

    def by_id(self, artifact_id: str) -> CohortFrontierArtifact:
        return next(item for item in self.artifacts if item.artifact_id == artifact_id)

    def by_kind(self, kind: CohortFrontierArtifactKind) -> tuple[CohortFrontierArtifact, ...]:
        return tuple(item for item in self.artifacts if item.kind is kind)

    @property
    def total_bytes(self) -> int:
        return sum(item.byte_estimate for item in self.artifacts)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"total_bytes": self.total_bytes}


def _artifact(artifact_id: str, kind: CohortFrontierArtifactKind, content: Any, parents: Iterable[str], summary: str) -> CohortFrontierArtifact:
    body_content = jsonable(content)
    body = {"artifact_id": artifact_id, "kind": kind, "content_address": content.content_address if hasattr(content, "content_address") else content_hash(body_content), "parent_addresses": tuple(sorted(set(parents))), "byte_estimate": len(str(body_content).encode("utf-8")), "summary": summary, "content": body_content}
    return CohortFrontierArtifact(**body, inventory_address=content_hash(body))


def build_cohort_frontier_artifact_inventory(fixture: CohortFrontierFixture, evaluation: CohortFrontierEvaluation, metrics: CohortFrontierMetricsReport, lineage: CohortFrontierLineageGraph, quality: CohortFrontierQualityGate, bundle: CohortFrontierReleaseBundle, release: CohortFrontierReleaseManifest) -> CohortFrontierArtifactInventory:
    fixture_artifact = _artifact("cohort-artifact-fixture", CohortFrontierArtifactKind.FIXTURE, fixture, (), "public aggregate fixture")
    evaluation_artifact = _artifact("cohort-artifact-evaluation", CohortFrontierArtifactKind.EVALUATION, evaluation, (fixture.content_address,), "positive/control replay")
    metrics_artifact = _artifact("cohort-artifact-metrics", CohortFrontierArtifactKind.METRICS, metrics, (evaluation.content_address,), "cohort coverage metrics")
    lineage_artifact = _artifact("cohort-artifact-lineage", CohortFrontierArtifactKind.LINEAGE, lineage, (fixture.content_address, evaluation.content_address), "source lineage")
    quality_artifact = _artifact("cohort-artifact-quality", CohortFrontierArtifactKind.QUALITY, quality, (evaluation.content_address, lineage.content_address), "blocking quality checks")
    bundle_artifact = _artifact("cohort-artifact-bundle", CohortFrontierArtifactKind.BUNDLE, bundle, (fixture.content_address, evaluation.content_address, metrics.content_address, lineage.content_address, quality.content_address), "release bundle")
    release_artifact = _artifact("cohort-artifact-release", CohortFrontierArtifactKind.RELEASE, release, (bundle.content_address, quality.content_address), "release manifest")
    artifacts = (fixture_artifact, evaluation_artifact, metrics_artifact, lineage_artifact, quality_artifact, bundle_artifact, release_artifact)
    body = {"artifacts": artifacts, "root_artifact_id": release_artifact.artifact_id}
    return CohortFrontierArtifactInventory(**body, content_address=content_hash(body))


__all__ = ["CohortFrontierArtifact", "CohortFrontierArtifactInventory", "CohortFrontierArtifactKind", "build_cohort_frontier_artifact_inventory"]
