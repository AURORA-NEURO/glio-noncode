"""Artifact inventory for C05-C08 release outputs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .causal_beta_frontier_bundle import CausalBetaFrontierReleaseBundle
from .causal_beta_frontier_fixture_eval import CausalBetaFrontierEvaluation
from .causal_beta_frontier_public_data import CausalBetaFrontierFixture
from .causal_beta_frontier_release import CausalBetaFrontierReleaseManifest
from .serialization import content_hash, jsonable


class CausalBetaFrontierArtifactKind(StrEnum):
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
    SCENARIOS = "scenarios"
    VALIDATION = "validation"
    BUNDLE = "bundle"
    RELEASE = "release"


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierArtifact:
    artifact_id: str
    kind: CausalBetaFrontierArtifactKind
    media_type: str
    relative_path: str
    content_address: str
    required: bool
    description: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierArtifactInventory:
    bundle_id: str
    release_id: str
    artifacts: tuple[CausalBetaFrontierArtifact, ...]
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

    def for_kind(self, kind: CausalBetaFrontierArtifactKind | str) -> tuple[CausalBetaFrontierArtifact, ...]:
        return tuple(item for item in self.artifacts if item.kind.value == str(kind))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"bundle_id": self.bundle_id, "release_id": self.release_id, "artifacts": [item.to_dict() for item in self.artifacts], "required_count": self.required_count, "resolved_count": self.resolved_count, "missing_artifact_ids": self.missing_artifact_ids, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _artifact(artifact_id: str, kind: CausalBetaFrontierArtifactKind, address: str, path: str, description: str) -> CausalBetaFrontierArtifact:
    return CausalBetaFrontierArtifact(artifact_id, kind, "application/json", path, address, True, description)


def build_causal_beta_frontier_artifact_inventory(fixture: CausalBetaFrontierFixture, evaluation: CausalBetaFrontierEvaluation, bundle: CausalBetaFrontierReleaseBundle, release: CausalBetaFrontierReleaseManifest) -> CausalBetaFrontierArtifactInventory:
    fields = (
        ("fixture", CausalBetaFrontierArtifactKind.FIXTURE, fixture.content_address, "fixture.json", "public aggregate fixture"),
        ("evaluation", CausalBetaFrontierArtifactKind.EVALUATION, evaluation.content_address, "evaluation.json", "deterministic replay"),
        ("metrics", CausalBetaFrontierArtifactKind.METRICS, bundle.metrics_address, "metrics.json", "operation metrics"),
        ("contracts", CausalBetaFrontierArtifactKind.CONTRACTS, bundle.contracts_address, "contracts.json", "capability contracts"),
        ("schema", CausalBetaFrontierArtifactKind.SCHEMA, bundle.schema_address, "schema.json", "input schema"),
        ("lineage", CausalBetaFrontierArtifactKind.LINEAGE, bundle.lineage_address, "lineage.json", "source lineage"),
        ("provenance", CausalBetaFrontierArtifactKind.PROVENANCE, bundle.provenance_address, "provenance.json", "provenance graph"),
        ("depth", CausalBetaFrontierArtifactKind.DEPTH, bundle.depth_address, "depth.json", "depth audit"),
        ("reconciliation", CausalBetaFrontierArtifactKind.RECONCILIATION, bundle.reconciliation_address, "reconciliation.json", "expected output alignment"),
        ("policy", CausalBetaFrontierArtifactKind.POLICY, bundle.policy_address, "policy.json", "bounded policy"),
        ("review", CausalBetaFrontierArtifactKind.REVIEW, bundle.review_address, "review.json", "review queue"),
        ("quality", CausalBetaFrontierArtifactKind.QUALITY, bundle.quality_gate_address, "quality.json", "quality gate"),
        ("scenarios", CausalBetaFrontierArtifactKind.SCENARIOS, bundle.scenario_address, "scenarios.json", "scenario matrix"),
        ("validation", CausalBetaFrontierArtifactKind.VALIDATION, bundle.validation_address, "validation.json", "validation matrix"),
        ("bundle", CausalBetaFrontierArtifactKind.BUNDLE, bundle.content_address, "bundle.json", "release bundle"),
        ("release", CausalBetaFrontierArtifactKind.RELEASE, release.content_address, "release.json", "release manifest"),
    )
    artifacts = tuple(_artifact(*item) for item in fields)
    return CausalBetaFrontierArtifactInventory(bundle.bundle_id, release.release_id, artifacts, len(artifacts), sum(bool(item.content_address) for item in artifacts), bool(artifacts) and all(item.content_address for item in artifacts))


__all__ = ["CausalBetaFrontierArtifact", "CausalBetaFrontierArtifactInventory", "CausalBetaFrontierArtifactKind", "build_causal_beta_frontier_artifact_inventory"]
