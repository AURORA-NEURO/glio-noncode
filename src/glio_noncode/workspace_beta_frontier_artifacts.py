"""Artifact inventory for the C05-C08 package."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workspace_beta_frontier_bundle import BetaFrontierReleaseBundle
from .workspace_beta_frontier_fixture_eval import BetaFrontierEvaluation
from .workspace_beta_frontier_metrics import BetaFrontierMetricsReport
from .workspace_beta_frontier_quality_gate import BetaFrontierQualityGate
from .workspace_beta_frontier_release import BetaFrontierReleaseManifest
from .workspace_beta_frontier_runtime import BetaFrontierRuntimeReport


class BetaFrontierArtifactKind(StrEnum):
    FIXTURE = "fixture"
    EVALUATION = "evaluation"
    METRICS = "metrics"
    QUALITY = "quality"
    RUNTIME = "runtime"
    BUNDLE = "bundle"
    RELEASE = "release"


@dataclass(frozen=True, slots=True)
class BetaFrontierArtifact:
    artifact_id: str
    kind: BetaFrontierArtifactKind
    media_type: str
    content_address: str
    size_hint: int
    retention: str
    content_hash: str

    def __post_init__(self) -> None:
        for name in ("artifact_id", "media_type", "content_address", "retention", "content_hash"):
            require_non_empty(str(getattr(self, name)), name)
        if self.size_hint < 0:
            raise ValueError("beta frontier artifact size hint cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BetaFrontierArtifactInventory:
    fixture_id: str
    artifacts: tuple[BetaFrontierArtifact, ...]
    accepted: bool
    missing_kinds: tuple[BetaFrontierArtifactKind, ...]
    content_address: str

    def by_kind(self, kind: BetaFrontierArtifactKind) -> BetaFrontierArtifact:
        return next(item for item in self.artifacts if item.kind is kind)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _artifact(kind: BetaFrontierArtifactKind, address: str, size_hint: int, retention: str) -> BetaFrontierArtifact:
    body = {"artifact_id": f"beta-artifact:{kind.value}", "kind": kind, "media_type": "application/json", "content_address": address, "size_hint": size_hint, "retention": retention}
    return BetaFrontierArtifact(**body, content_hash=content_hash(body))


def build_beta_frontier_artifact_inventory(fixture_id: str, fixture_address: str, evaluation: BetaFrontierEvaluation, metrics: BetaFrontierMetricsReport, quality: BetaFrontierQualityGate, runtime: BetaFrontierRuntimeReport, bundle: BetaFrontierReleaseBundle, release: BetaFrontierReleaseManifest) -> BetaFrontierArtifactInventory:
    values = (
        _artifact(BetaFrontierArtifactKind.FIXTURE, fixture_address, 16, "fixture-version"),
        _artifact(BetaFrontierArtifactKind.EVALUATION, evaluation.content_address, len(evaluation.checks), "run-retained"),
        _artifact(BetaFrontierArtifactKind.METRICS, metrics.content_address, len(metrics.metrics), "run-retained"),
        _artifact(BetaFrontierArtifactKind.QUALITY, quality.content_address, len(quality.checks), "release-retained"),
        _artifact(BetaFrontierArtifactKind.RUNTIME, runtime.content_address, len(runtime.stages), "run-retained"),
        _artifact(BetaFrontierArtifactKind.BUNDLE, bundle.content_address, 1, "release-retained"),
        _artifact(BetaFrontierArtifactKind.RELEASE, release.content_address, len(release.checks), "release-retained"),
    )
    required = set(BetaFrontierArtifactKind)
    missing = tuple(sorted(required - {item.kind for item in values}, key=lambda item: item.value))
    body = {"fixture_id": fixture_id, "artifacts": values, "accepted": not missing, "missing_kinds": missing}
    return BetaFrontierArtifactInventory(**body, content_address=content_hash(body))


__all__ = ["BetaFrontierArtifact", "BetaFrontierArtifactInventory", "BetaFrontierArtifactKind", "build_beta_frontier_artifact_inventory"]
