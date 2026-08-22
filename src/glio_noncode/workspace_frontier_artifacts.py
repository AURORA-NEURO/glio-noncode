"""Artifact inventory for workspace frontier release and review outputs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable
from .workspace_frontier_bundle import WorkspaceFrontierReleaseBundle
from .workspace_frontier_fixture_eval import WorkspaceFrontierEvaluation
from .workspace_frontier_metrics import WorkspaceFrontierMetricsReport
from .workspace_frontier_quality_gate import WorkspaceFrontierQualityGate
from .workspace_frontier_release import WorkspaceFrontierReleaseManifest
from .workspace_frontier_runtime import WorkspaceFrontierRuntimeReport


class WorkspaceFrontierArtifactKind(StrEnum):
    FIXTURE = "fixture"
    EVALUATION = "evaluation"
    METRICS = "metrics"
    QUALITY = "quality"
    RUNTIME = "runtime"
    BUNDLE = "bundle"
    RELEASE = "release"


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierArtifact:
    artifact_id: str
    kind: WorkspaceFrontierArtifactKind
    content_address: str
    depends_on: tuple[str, ...]
    public: bool
    content_hash: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierArtifactInventory:
    fixture_id: str
    artifacts: tuple[WorkspaceFrontierArtifact, ...]
    root_artifact_id: str
    content_address: str

    def by_kind(self, kind: WorkspaceFrontierArtifactKind) -> tuple[WorkspaceFrontierArtifact, ...]:
        return tuple(item for item in self.artifacts if item.kind is kind)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _artifact(artifact_id: str, kind: WorkspaceFrontierArtifactKind, address: str, depends_on: tuple[str, ...], public: bool) -> WorkspaceFrontierArtifact:
    body = {"artifact_id": artifact_id, "kind": kind, "content_address": address, "depends_on": depends_on, "public": public}
    return WorkspaceFrontierArtifact(**body, content_hash=content_hash(body))


def build_workspace_frontier_artifact_inventory(fixture_id: str, fixture_address: str, evaluation: WorkspaceFrontierEvaluation, metrics: WorkspaceFrontierMetricsReport, quality: WorkspaceFrontierQualityGate, runtime: WorkspaceFrontierRuntimeReport, bundle: WorkspaceFrontierReleaseBundle, release: WorkspaceFrontierReleaseManifest) -> WorkspaceFrontierArtifactInventory:
    artifacts = (
        _artifact("workspace-artifact-fixture", WorkspaceFrontierArtifactKind.FIXTURE, fixture_address, (), True),
        _artifact("workspace-artifact-evaluation", WorkspaceFrontierArtifactKind.EVALUATION, evaluation.content_address, ("workspace-artifact-fixture",), True),
        _artifact("workspace-artifact-metrics", WorkspaceFrontierArtifactKind.METRICS, metrics.content_address, ("workspace-artifact-evaluation",), True),
        _artifact("workspace-artifact-quality", WorkspaceFrontierArtifactKind.QUALITY, quality.content_address, ("workspace-artifact-evaluation",), True),
        _artifact("workspace-artifact-runtime", WorkspaceFrontierArtifactKind.RUNTIME, runtime.content_address, ("workspace-artifact-evaluation", "workspace-artifact-metrics"), True),
        _artifact("workspace-artifact-bundle", WorkspaceFrontierArtifactKind.BUNDLE, bundle.content_address, ("workspace-artifact-fixture", "workspace-artifact-evaluation", "workspace-artifact-metrics"), True),
        _artifact("workspace-artifact-release", WorkspaceFrontierArtifactKind.RELEASE, release.content_address, ("workspace-artifact-bundle", "workspace-artifact-quality", "workspace-artifact-runtime"), True),
    )
    body = {"fixture_id": fixture_id, "artifacts": artifacts, "root_artifact_id": "workspace-artifact-release"}
    return WorkspaceFrontierArtifactInventory(fixture_id=fixture_id, artifacts=artifacts, root_artifact_id="workspace-artifact-release", content_address=content_hash(body))


__all__ = ["WorkspaceFrontierArtifact", "WorkspaceFrontierArtifactInventory", "WorkspaceFrontierArtifactKind", "build_workspace_frontier_artifact_inventory"]
