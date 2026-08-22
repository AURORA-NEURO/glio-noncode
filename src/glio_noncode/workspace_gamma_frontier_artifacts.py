"""Artifact inventory and retention declarations for the frontier bundle."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workspace_gamma_frontier_bundle import GammaFrontierEvidenceBundle
from .workspace_gamma_frontier_release import GammaFrontierReleaseManifest
from .workspace_gamma_frontier_runtime import GammaFrontierRuntimeReport


class GammaFrontierArtifactKind(StrEnum):
    """Published artifact categories."""

    FIXTURE = "fixture"
    DATA_AUDIT = "data_audit"
    EVALUATION = "evaluation"
    METRICS = "metrics"
    POLICY = "policy"
    LINEAGE = "lineage"
    RECONCILIATION = "reconciliation"
    PROJECTION_AUDIT = "projection_audit"
    QUALITY_GATE = "quality_gate"
    RUNTIME = "runtime"
    RELEASE = "release"


@dataclass(frozen=True, slots=True)
class GammaFrontierArtifact:
    """One addressed artifact with retention and sensitivity declarations."""

    artifact_id: str
    kind: GammaFrontierArtifactKind
    address: str
    size_hint: int
    retention: str
    sensitivity: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.artifact_id, "artifact_id")
        require_non_empty(self.address, "address")
        require_non_empty(self.retention, "retention")
        require_non_empty(self.sensitivity, "sensitivity")
        if self.size_hint < 0:
            raise ValueError("artifact size hint cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GammaFrontierArtifactInventory:
    """Inventory with complete-kind and address checks."""

    fixture_id: str
    artifacts: tuple[GammaFrontierArtifact, ...]
    accepted: bool
    content_address: str

    def by_kind(self, kind: GammaFrontierArtifactKind) -> GammaFrontierArtifact:
        return next(item for item in self.artifacts if item.kind is kind)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "artifact_count": len(self.artifacts),
            "kind_count": len({item.kind for item in self.artifacts}),
        }


def _artifact(
    index: int,
    kind: GammaFrontierArtifactKind,
    address: str,
    size_hint: int,
    retention: str,
    sensitivity: str = "public_aggregate",
) -> GammaFrontierArtifact:
    body = {
        "artifact_id": f"gamma-artifact-{index:03d}",
        "kind": kind,
        "address": address,
        "size_hint": size_hint,
        "retention": retention,
        "sensitivity": sensitivity,
    }
    return GammaFrontierArtifact(**body, content_address=content_hash(body, prefix="artifact"))


def build_gamma_frontier_artifact_inventory(
    runtime: GammaFrontierRuntimeReport,
    bundle: GammaFrontierEvidenceBundle,
    release: GammaFrontierReleaseManifest | None = None,
) -> GammaFrontierArtifactInventory:
    """Declare all runtime outputs and their retention behavior."""

    address_map = {str(item.kind): item.address for item in bundle.entries}
    artifacts = [
        _artifact(
            1,
            GammaFrontierArtifactKind.FIXTURE,
            address_map.get("fixture", ""),
            16,
            "retain-with-release",
        ),
        _artifact(
            2,
            GammaFrontierArtifactKind.DATA_AUDIT,
            runtime.data_audit.content_address,
            7,
            "retain-with-release",
        ),
        _artifact(
            3,
            GammaFrontierArtifactKind.EVALUATION,
            runtime.evaluation.content_address,
            16,
            "retain-with-release",
        ),
        _artifact(
            4,
            GammaFrontierArtifactKind.METRICS,
            runtime.metrics.content_address,
            len(runtime.metrics.metrics),
            "retain-with-release",
        ),
        _artifact(
            5,
            GammaFrontierArtifactKind.POLICY,
            content_hash(runtime.policy_decisions, prefix="policy-inventory"),
            len(runtime.policy_decisions),
            "retain-with-release",
        ),
        _artifact(
            6,
            GammaFrontierArtifactKind.LINEAGE,
            runtime.lineage.content_address,
            len(runtime.lineage.edges),
            "retain-with-release",
        ),
        _artifact(
            7,
            GammaFrontierArtifactKind.RECONCILIATION,
            runtime.reconciliation.content_address,
            len(runtime.reconciliation.items),
            "retain-with-release",
        ),
        _artifact(
            8,
            GammaFrontierArtifactKind.PROJECTION_AUDIT,
            runtime.projection_audit.content_address,
            len(runtime.projection_audit.assertions),
            "retain-with-release",
        ),
        _artifact(
            9,
            GammaFrontierArtifactKind.QUALITY_GATE,
            runtime.quality.content_address,
            len(runtime.quality.checks),
            "retain-with-release",
        ),
        _artifact(
            10,
            GammaFrontierArtifactKind.RUNTIME,
            runtime.content_address,
            len(runtime.stages),
            "retain-with-release",
        ),
    ]
    if release is not None:
        artifacts.append(
            _artifact(
                11,
                GammaFrontierArtifactKind.RELEASE,
                release.content_address,
                len(release.checks),
                "retain-with-release",
            )
        )
    accepted = all(":" in item.address for item in artifacts)
    body = {"fixture_id": runtime.fixture_id, "artifacts": tuple(artifacts), "accepted": accepted}
    return GammaFrontierArtifactInventory(
        **body, content_address=content_hash(body, prefix="inventory")
    )


__all__ = [
    "GammaFrontierArtifact",
    "GammaFrontierArtifactInventory",
    "GammaFrontierArtifactKind",
    "build_gamma_frontier_artifact_inventory",
]
