"""Artifact inventory for Domain 14 lifecycle release evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .evidence_lifecycle_frontier_bundle import EvidenceLifecycleReleaseBundle
from .evidence_lifecycle_frontier_fixture_eval import EvidenceLifecycleEvaluation
from .evidence_lifecycle_frontier_metrics import EvidenceLifecycleMetricsReport
from .evidence_lifecycle_frontier_public_data import EvidenceLifecycleFixture
from .evidence_lifecycle_frontier_quality_gate import EvidenceLifecycleQualityGate
from .evidence_lifecycle_frontier_release import EvidenceLifecycleReleaseManifest
from .evidence_lifecycle_frontier_runtime import EvidenceLifecycleRuntimeReport
from .serialization import content_hash, jsonable


class EvidenceLifecycleArtifactKind(StrEnum):
    FIXTURE = "fixture"
    EVALUATION = "evaluation"
    METRICS = "metrics"
    QUALITY_GATE = "quality_gate"
    RUNTIME = "runtime"
    RELEASE = "release"
    BUNDLE = "bundle"


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleArtifact:
    artifact_id: str
    kind: EvidenceLifecycleArtifactKind
    content_address: str
    parent_ids: tuple[str, ...]
    accepted: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleArtifactInventory:
    root_artifact_id: str
    artifacts: tuple[EvidenceLifecycleArtifact, ...]
    content_address: str

    def by_kind(self, kind: EvidenceLifecycleArtifactKind) -> tuple[EvidenceLifecycleArtifact, ...]:
        return tuple(item for item in self.artifacts if item.kind is kind)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_evidence_lifecycle_artifact_inventory(fixture: EvidenceLifecycleFixture, evaluation: EvidenceLifecycleEvaluation, metrics: EvidenceLifecycleMetricsReport, gate: EvidenceLifecycleQualityGate, runtime: EvidenceLifecycleRuntimeReport, release: EvidenceLifecycleReleaseManifest, bundle: EvidenceLifecycleReleaseBundle) -> EvidenceLifecycleArtifactInventory:
    rows = (("evidence-artifact-fixture", EvidenceLifecycleArtifactKind.FIXTURE, fixture.content_address, (), True), ("evidence-artifact-evaluation", EvidenceLifecycleArtifactKind.EVALUATION, evaluation.content_address, ("evidence-artifact-fixture",), evaluation.accepted), ("evidence-artifact-metrics", EvidenceLifecycleArtifactKind.METRICS, metrics.content_address, ("evidence-artifact-evaluation",), True), ("evidence-artifact-quality", EvidenceLifecycleArtifactKind.QUALITY_GATE, gate.content_address, ("evidence-artifact-evaluation",), gate.accepted), ("evidence-artifact-runtime", EvidenceLifecycleArtifactKind.RUNTIME, runtime.content_address, ("evidence-artifact-quality",), runtime.accepted), ("evidence-artifact-release", EvidenceLifecycleArtifactKind.RELEASE, release.content_address, ("evidence-artifact-runtime",), release.accepted), ("evidence-artifact-bundle", EvidenceLifecycleArtifactKind.BUNDLE, bundle.content_address, ("evidence-artifact-release",), bundle.publishable))
    artifacts = tuple(EvidenceLifecycleArtifact(*row) for row in rows)
    body = {"root_artifact_id": "evidence-artifact-release", "artifacts": artifacts}
    return EvidenceLifecycleArtifactInventory(**body, content_address=content_hash(body))


__all__ = ["EvidenceLifecycleArtifact", "EvidenceLifecycleArtifactInventory", "EvidenceLifecycleArtifactKind", "build_evidence_lifecycle_artifact_inventory"]
