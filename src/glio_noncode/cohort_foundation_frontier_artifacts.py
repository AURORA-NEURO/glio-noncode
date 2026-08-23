"""Artifact inventory for reproducible C01-C04 handoff."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_bundle import CohortFoundationReleaseBundle
from .cohort_foundation_frontier_release import CohortFoundationReleaseManifest


class CohortFoundationArtifactKind(StrEnum):
    FIXTURE = "fixture"
    EVALUATION = "evaluation"
    METRICS = "metrics"
    LINEAGE = "lineage"
    PROVENANCE = "provenance"
    POLICY = "policy"
    RECONCILIATION = "reconciliation"
    QUALITY = "quality"
    REVIEW = "review"
    BUNDLE = "bundle"
    RELEASE = "release"


@dataclass(frozen=True, slots=True)
class CohortFoundationArtifact:
    artifact_id: str
    kind: CohortFoundationArtifactKind
    content_address: str
    parent_addresses: tuple[str, ...]
    description: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationArtifactInventory:
    root_artifact_id: str
    artifacts: tuple[CohortFoundationArtifact, ...]
    complete: bool
    content_address: str

    def by_kind(self, kind: CohortFoundationArtifactKind) -> tuple[CohortFoundationArtifact, ...]:
        return tuple(item for item in self.artifacts if item.kind is kind)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_foundation_frontier_artifact_inventory(bundle: CohortFoundationReleaseBundle, release: CohortFoundationReleaseManifest) -> CohortFoundationArtifactInventory:
    values = (
        ("cohort-foundation-artifact-fixture", CohortFoundationArtifactKind.FIXTURE, bundle.fixture.content_address, (), "public aggregate fixture"),
        ("cohort-foundation-artifact-evaluation", CohortFoundationArtifactKind.EVALUATION, bundle.evaluation.content_address, (bundle.fixture.content_address,), "record executions"),
        ("cohort-foundation-artifact-metrics", CohortFoundationArtifactKind.METRICS, bundle.metrics.content_address, (bundle.evaluation.content_address,), "operation coverage metrics"),
        ("cohort-foundation-artifact-lineage", CohortFoundationArtifactKind.LINEAGE, bundle.lineage.content_address, (bundle.fixture.content_address, bundle.evaluation.content_address), "source and execution graph"),
        ("cohort-foundation-artifact-provenance", CohortFoundationArtifactKind.PROVENANCE, bundle.provenance.content_address, (bundle.lineage.content_address,), "source receipts"),
        ("cohort-foundation-artifact-policy", CohortFoundationArtifactKind.POLICY, bundle.policy.content_address, (bundle.evaluation.content_address,), "policy decisions"),
        ("cohort-foundation-artifact-reconciliation", CohortFoundationArtifactKind.RECONCILIATION, bundle.reconciliation.content_address, (bundle.policy.content_address,), "expected versus observed states"),
        ("cohort-foundation-artifact-quality", CohortFoundationArtifactKind.QUALITY, bundle.quality.content_address, (bundle.reconciliation.content_address,), "blocking quality gate"),
        ("cohort-foundation-artifact-review", CohortFoundationArtifactKind.REVIEW, bundle.review.content_address, (bundle.policy.content_address,), "review queue"),
        ("cohort-foundation-artifact-bundle", CohortFoundationArtifactKind.BUNDLE, bundle.content_address, (bundle.quality.content_address,), "release bundle"),
        ("cohort-foundation-artifact-release", CohortFoundationArtifactKind.RELEASE, release.content_address, (bundle.content_address,), "release manifest"),
    )
    artifacts = tuple(CohortFoundationArtifact(artifact_id, kind, address, parents, description) for artifact_id, kind, address, parents, description in values)
    body = {"root": "cohort-foundation-artifact-release", "artifacts": artifacts}
    return CohortFoundationArtifactInventory(body["root"], artifacts, len(artifacts) == len(CohortFoundationArtifactKind), content_hash(body))


__all__ = ["CohortFoundationArtifact", "CohortFoundationArtifactInventory", "CohortFoundationArtifactKind", "build_cohort_foundation_frontier_artifact_inventory"]
