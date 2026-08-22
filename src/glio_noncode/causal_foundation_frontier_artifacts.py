"""Artifact inventory and deterministic export projections."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .causal_foundation_frontier_bundle import CausalFoundationFrontierReleaseBundle
from .causal_foundation_frontier_fixture_eval import CausalFoundationFrontierEvaluation
from .causal_foundation_frontier_public_data import CausalFoundationFrontierFixture
from .causal_foundation_frontier_release import CausalFoundationFrontierReleaseManifest
from .serialization import content_hash, jsonable


class CausalFoundationFrontierArtifactKind(StrEnum):
    FIXTURE = "fixture"
    EVALUATION = "evaluation"
    METRICS = "metrics"
    CONTRACTS = "contracts"
    SCHEMA = "schema"
    LINEAGE = "lineage"
    PROVENANCE = "provenance"
    DEPTH = "depth"
    RECONCILIATION = "reconciliation"
    POLICY = "policy"
    REVIEW = "review"
    QUALITY = "quality"
    BUNDLE = "bundle"
    RELEASE = "release"
    REVIEW_CSV = "review_csv"
    SUMMARY = "summary"


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierArtifact:
    artifact_id: str
    kind: CausalFoundationFrontierArtifactKind
    media_type: str
    relative_path: str
    content_address: str
    required: bool
    description: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierArtifactInventory:
    bundle_id: str
    release_id: str
    artifacts: tuple[CausalFoundationFrontierArtifact, ...]
    required_count: int
    resolved_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def missing_artifact_ids(self) -> tuple[str, ...]:
        return tuple(item.artifact_id for item in self.artifacts if not item.content_address)

    def for_kind(self, kind: CausalFoundationFrontierArtifactKind | str) -> tuple[CausalFoundationFrontierArtifact, ...]:
        return tuple(item for item in self.artifacts if item.kind.value == str(kind))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"bundle_id": self.bundle_id, "release_id": self.release_id, "artifacts": [item.to_dict() for item in self.artifacts], "required_count": self.required_count, "resolved_count": self.resolved_count, "missing_artifact_ids": self.missing_artifact_ids, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _artifact(artifact_id: str, kind: CausalFoundationFrontierArtifactKind, path: str, address: str, description: str, media_type: str = "application/json") -> CausalFoundationFrontierArtifact:
    return CausalFoundationFrontierArtifact(artifact_id, kind, media_type, path, address, True, description)


def build_causal_foundation_frontier_artifact_inventory(fixture: CausalFoundationFrontierFixture, evaluation: CausalFoundationFrontierEvaluation, bundle: CausalFoundationFrontierReleaseBundle, release: CausalFoundationFrontierReleaseManifest, *, review_csv_address: str = "sha256:pending", summary_address: str = "sha256:pending") -> CausalFoundationFrontierArtifactInventory:
    fields = (
        ("fixture", CausalFoundationFrontierArtifactKind.FIXTURE, fixture.content_address, "fixture.json", "public aggregate input fixture"),
        ("evaluation", CausalFoundationFrontierArtifactKind.EVALUATION, evaluation.content_address, "evaluation.json", "deterministic row replay"),
        ("metrics", CausalFoundationFrontierArtifactKind.METRICS, bundle.metrics_address, "metrics.json", "state and issue metrics"),
        ("contracts", CausalFoundationFrontierArtifactKind.CONTRACTS, bundle.contracts_address, "contracts.json", "operation contracts"),
        ("schema", CausalFoundationFrontierArtifactKind.SCHEMA, bundle.schema_address, "schema.json", "record envelope schema"),
        ("lineage", CausalFoundationFrontierArtifactKind.LINEAGE, bundle.lineage_address, "lineage.json", "source-to-result edges"),
        ("provenance", CausalFoundationFrontierArtifactKind.PROVENANCE, bundle.provenance_address, "provenance.json", "content-addressed provenance graph"),
        ("depth", CausalFoundationFrontierArtifactKind.DEPTH, bundle.depth_address, "depth.json", "implementation depth audit"),
        ("reconciliation", CausalFoundationFrontierArtifactKind.RECONCILIATION, bundle.reconciliation_address, "reconciliation.json", "expected and observed alignment"),
        ("policy", CausalFoundationFrontierArtifactKind.POLICY, bundle.policy_address, "policy.json", "bounded disposition rules"),
        ("review", CausalFoundationFrontierArtifactKind.REVIEW, bundle.review_address, "review.json", "control review queue"),
        ("quality", CausalFoundationFrontierArtifactKind.QUALITY, bundle.quality_gate_address, "quality.json", "release quality gate"),
        ("bundle", CausalFoundationFrontierArtifactKind.BUNDLE, bundle.content_address, "bundle.json", "release bundle"),
        ("release", CausalFoundationFrontierArtifactKind.RELEASE, release.content_address, "release.json", "release manifest"),
        ("review-csv", CausalFoundationFrontierArtifactKind.REVIEW_CSV, review_csv_address, "review.csv", "tabular review projection", "text/csv"),
        ("summary", CausalFoundationFrontierArtifactKind.SUMMARY, summary_address, "summary.json", "summary projection"),
    )
    artifacts = tuple(_artifact(artifact_id, kind, path, address, description, media_type) for artifact_id, kind, address, path, description, *rest in fields for media_type in (rest[0] if rest else "application/json",))
    return CausalFoundationFrontierArtifactInventory(bundle.bundle_id, release.release_id, artifacts, sum(item.required for item in artifacts), sum(bool(item.content_address) for item in artifacts), bool(artifacts) and all(item.content_address for item in artifacts))


__all__ = ["CausalFoundationFrontierArtifact", "CausalFoundationFrontierArtifactInventory", "CausalFoundationFrontierArtifactKind", "build_causal_foundation_frontier_artifact_inventory"]
