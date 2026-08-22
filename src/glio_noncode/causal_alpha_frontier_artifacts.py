"""Artifact inventory for the alpha frontier release."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .causal_alpha_frontier_bundle import CausalAlphaFrontierReleaseBundle
from .causal_alpha_frontier_controls import CausalAlphaFrontierControlCoverage
from .causal_alpha_frontier_diagnostics import CausalAlphaFrontierDiagnosticReport
from .causal_alpha_frontier_fixture_eval import CausalAlphaFrontierFixtureEvaluation
from .causal_alpha_frontier_public_data import CausalAlphaFrontierFixture
from .causal_alpha_frontier_release import CausalAlphaFrontierReleaseManifest
from .causal_alpha_frontier_projections import CausalAlphaFrontierProjectionReport
from .causal_alpha_frontier_traces import CausalAlphaFrontierTraceLedger
from .serialization import content_hash, jsonable


class CausalAlphaFrontierArtifactKind(StrEnum):
    FIXTURE = "fixture"
    EVALUATION = "evaluation"
    CONTROL_COVERAGE = "control_coverage"
    DECISION_TRACES = "decision_traces"
    PROJECTIONS = "projections"
    DIAGNOSTICS = "diagnostics"
    METRICS = "metrics"
    CONTRACTS = "contracts"
    SCHEMA = "schema"
    LINEAGE = "lineage"
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
class CausalAlphaFrontierArtifact:
    artifact_id: str
    kind: CausalAlphaFrontierArtifactKind
    media_type: str
    relative_path: str
    content_address: str
    required: bool
    description: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierArtifactInventory:
    bundle_id: str
    release_id: str
    artifacts: tuple[CausalAlphaFrontierArtifact, ...]
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

    def for_kind(self, kind: CausalAlphaFrontierArtifactKind | str) -> tuple[CausalAlphaFrontierArtifact, ...]:
        return tuple(item for item in self.artifacts if item.kind.value == str(kind))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"bundle_id": self.bundle_id, "release_id": self.release_id, "artifacts": [item.to_dict() for item in self.artifacts], "required_count": self.required_count, "resolved_count": self.resolved_count, "missing_artifact_ids": self.missing_artifact_ids, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _artifact(artifact_id: str, kind: CausalAlphaFrontierArtifactKind, address: str, path: str, description: str) -> CausalAlphaFrontierArtifact:
    return CausalAlphaFrontierArtifact(artifact_id, kind, "application/json", path, address, True, description)


def build_causal_alpha_frontier_artifact_inventory(fixture: CausalAlphaFrontierFixture, evaluation: CausalAlphaFrontierFixtureEvaluation, bundle: CausalAlphaFrontierReleaseBundle, release: CausalAlphaFrontierReleaseManifest, controls: CausalAlphaFrontierControlCoverage | None = None, traces: CausalAlphaFrontierTraceLedger | None = None, projections: CausalAlphaFrontierProjectionReport | None = None, diagnostics: CausalAlphaFrontierDiagnosticReport | None = None) -> CausalAlphaFrontierArtifactInventory:
    fields = (
        ("fixture", CausalAlphaFrontierArtifactKind.FIXTURE, fixture.content_address, "fixture.json", "public aggregate fixture"),
        ("evaluation", CausalAlphaFrontierArtifactKind.EVALUATION, evaluation.content_address, "evaluation.json", "deterministic evaluation"),
        ("control-coverage", CausalAlphaFrontierArtifactKind.CONTROL_COVERAGE, controls.content_address if controls else "", "control-coverage.json", "control class coverage"),
        ("decision-traces", CausalAlphaFrontierArtifactKind.DECISION_TRACES, traces.content_address if traces else "", "decision-traces.json", "per-row transformation traces"),
        ("projections", CausalAlphaFrontierArtifactKind.PROJECTIONS, projections.content_address if projections else "", "projections.json", "faceted review projections"),
        ("diagnostics", CausalAlphaFrontierArtifactKind.DIAGNOSTICS, diagnostics.content_address if diagnostics else "", "diagnostics.json", "cross-plane release diagnostics"),
        ("metrics", CausalAlphaFrontierArtifactKind.METRICS, bundle.metrics.content_address, "metrics.json", "operation metrics"),
        ("contracts", CausalAlphaFrontierArtifactKind.CONTRACTS, bundle.contracts.content_address, "contracts.json", "capability contracts"),
        ("schema", CausalAlphaFrontierArtifactKind.SCHEMA, bundle.schema.content_address, "schema.json", "record schema"),
        ("lineage", CausalAlphaFrontierArtifactKind.LINEAGE, bundle.lineage.content_address, "lineage.json", "source lineage"),
        ("depth", CausalAlphaFrontierArtifactKind.DEPTH, bundle.depth.content_address, "depth.json", "depth audit"),
        ("reconciliation", CausalAlphaFrontierArtifactKind.RECONCILIATION, bundle.reconciliation.content_address, "reconciliation.json", "expected state alignment"),
        ("policy", CausalAlphaFrontierArtifactKind.POLICY, bundle.policy.content_address, "policy.json", "bounded dispositions"),
        ("review", CausalAlphaFrontierArtifactKind.REVIEW, bundle.review.content_address, "review.json", "review queue"),
        ("quality", CausalAlphaFrontierArtifactKind.QUALITY, bundle.quality.content_address, "quality.json", "quality gate"),
        ("scenarios", CausalAlphaFrontierArtifactKind.SCENARIOS, bundle.scenario.content_address, "scenarios.json", "scenario matrix"),
        ("validation", CausalAlphaFrontierArtifactKind.VALIDATION, bundle.validation.content_address, "validation.json", "validation matrix"),
        ("bundle", CausalAlphaFrontierArtifactKind.BUNDLE, bundle.content_address, "bundle.json", "release bundle"),
        ("release", CausalAlphaFrontierArtifactKind.RELEASE, release.content_address, "release.json", "release manifest"),
    )
    artifacts = tuple(_artifact(*item) for item in fields)
    return CausalAlphaFrontierArtifactInventory(bundle.bundle_id, release.release_id, artifacts, len(artifacts), sum(bool(item.content_address) for item in artifacts), bool(artifacts) and all(item.content_address for item in artifacts))


__all__ = ["CausalAlphaFrontierArtifact", "CausalAlphaFrontierArtifactInventory", "CausalAlphaFrontierArtifactKind", "build_causal_alpha_frontier_artifact_inventory"]
