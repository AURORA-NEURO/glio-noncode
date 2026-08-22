"""Artifact inventory for Domain 13 release evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable
from .validation_frontier_fixture_eval import ValidationFrontierEvaluation
from .validation_frontier_lineage import ValidationFrontierLineageGraph
from .validation_frontier_metrics import ValidationFrontierMetricsReport
from .validation_frontier_public_data import ValidationFrontierFixture
from .validation_frontier_quality_gate import ValidationFrontierQualityGate
from .validation_frontier_release import ValidationFrontierReleaseManifest
from .validation_frontier_runtime import ValidationFrontierRuntimeReport


class ValidationFrontierArtifactKind(StrEnum):
    FIXTURE = "fixture"
    EVALUATION = "evaluation"
    METRICS = "metrics"
    LINEAGE = "lineage"
    QUALITY = "quality"
    RUNTIME = "runtime"
    RELEASE = "release"


@dataclass(frozen=True, slots=True)
class ValidationFrontierArtifact:
    artifact_id: str
    kind: ValidationFrontierArtifactKind
    content_address: str
    byte_count: int
    parent_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationFrontierArtifactInventory:
    artifacts: tuple[ValidationFrontierArtifact, ...]
    root_artifact_id: str
    total_bytes: int
    content_address: str

    def by_kind(self, kind: ValidationFrontierArtifactKind) -> tuple[ValidationFrontierArtifact, ...]:
        return tuple(item for item in self.artifacts if item.kind is kind)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_frontier_artifact_inventory(fixture: ValidationFrontierFixture, evaluation: ValidationFrontierEvaluation, metrics: ValidationFrontierMetricsReport, lineage: ValidationFrontierLineageGraph, quality: ValidationFrontierQualityGate, runtime: ValidationFrontierRuntimeReport, release: ValidationFrontierReleaseManifest) -> ValidationFrontierArtifactInventory:
    values = (("validation-artifact-fixture", ValidationFrontierArtifactKind.FIXTURE, fixture.content_address, fixture, ()), ("validation-artifact-evaluation", ValidationFrontierArtifactKind.EVALUATION, evaluation.content_address, evaluation, ("validation-artifact-fixture",)), ("validation-artifact-metrics", ValidationFrontierArtifactKind.METRICS, metrics.content_address, metrics, ("validation-artifact-evaluation",)), ("validation-artifact-lineage", ValidationFrontierArtifactKind.LINEAGE, lineage.content_address, lineage, ("validation-artifact-evaluation",)), ("validation-artifact-quality", ValidationFrontierArtifactKind.QUALITY, quality.content_address, quality, ("validation-artifact-evaluation", "validation-artifact-lineage")), ("validation-artifact-runtime", ValidationFrontierArtifactKind.RUNTIME, runtime.content_address, runtime, ("validation-artifact-quality",)), ("validation-artifact-release", ValidationFrontierArtifactKind.RELEASE, release.content_address, release, ("validation-artifact-runtime", "validation-artifact-quality")))
    artifacts = tuple(ValidationFrontierArtifact(artifact_id, kind, address, len(str(jsonable(value)).encode("utf-8")), parents) for artifact_id, kind, address, value, parents in values)
    body = {"artifacts": artifacts, "root_artifact_id": "validation-artifact-release", "total_bytes": sum(item.byte_count for item in artifacts)}
    return ValidationFrontierArtifactInventory(**body, content_address=content_hash(body))


__all__ = ["ValidationFrontierArtifact", "ValidationFrontierArtifactInventory", "ValidationFrontierArtifactKind", "build_validation_frontier_artifact_inventory"]
