"""Ordered runtime rehearsal that exercises every C01-C04 release surface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_foundation_frontier_adapters import build_causal_foundation_frontier_adapters
from .causal_foundation_frontier_artifacts import CausalFoundationFrontierArtifactInventory, build_causal_foundation_frontier_artifact_inventory
from .causal_foundation_frontier_bundle import CausalFoundationFrontierReleaseBundle, assemble_causal_foundation_frontier_bundle
from .causal_foundation_frontier_contracts import CausalFoundationFrontierContractReport, build_causal_foundation_frontier_contracts
from .causal_foundation_frontier_depth import CausalFoundationFrontierDepthAudit, audit_causal_foundation_frontier_depth
from .causal_foundation_frontier_fixture_eval import CausalFoundationFrontierEvaluation, evaluate_causal_foundation_frontier_fixture
from .causal_foundation_frontier_lineage import CausalFoundationFrontierLineage, build_causal_foundation_frontier_lineage
from .causal_foundation_frontier_metrics import CausalFoundationFrontierMetrics, build_causal_foundation_frontier_metrics
from .causal_foundation_frontier_observability import CausalFoundationFrontierEvent, build_causal_foundation_frontier_observability, record_causal_foundation_frontier_event
from .causal_foundation_frontier_policy import CausalFoundationFrontierPolicy, default_causal_foundation_frontier_policy
from .causal_foundation_frontier_provenance import CausalFoundationFrontierProvenanceGraph, build_causal_foundation_frontier_provenance
from .causal_foundation_frontier_quality_gate import CausalFoundationFrontierQualityGate, evaluate_causal_foundation_frontier_quality
from .causal_foundation_frontier_public_data import CausalFoundationFrontierFixture, audit_causal_foundation_frontier_data, default_causal_foundation_frontier_fixture
from .causal_foundation_frontier_reconciliation import CausalFoundationFrontierReconciliation, reconcile_causal_foundation_frontier
from .causal_foundation_frontier_release import CausalFoundationFrontierReleaseManifest, build_causal_foundation_frontier_release_manifest
from .causal_foundation_frontier_review import CausalFoundationFrontierReviewQueue, build_causal_foundation_frontier_review_queue
from .causal_foundation_frontier_schema import CausalFoundationFrontierSchemaReport, validate_causal_foundation_frontier_schema
from .causal_foundation_frontier_views import CausalFoundationFrontierReviewView, CausalFoundationFrontierSummaryView, build_causal_foundation_frontier_review_view, build_causal_foundation_frontier_summary_view
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierRuntimeStage:
    stage_id: str
    sequence: int
    state: str
    output_address: str
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"stage_id": self.stage_id, "sequence": self.sequence, "state": self.state, "output_address": self.output_address, "detail": self.detail}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierRuntimeReport:
    run_id: str
    fixture: CausalFoundationFrontierFixture
    evaluation: CausalFoundationFrontierEvaluation
    metrics: CausalFoundationFrontierMetrics
    contracts: CausalFoundationFrontierContractReport
    schema: CausalFoundationFrontierSchemaReport
    lineage: CausalFoundationFrontierLineage
    provenance: CausalFoundationFrontierProvenanceGraph
    depth: CausalFoundationFrontierDepthAudit
    policy: CausalFoundationFrontierPolicy
    decisions: tuple[Any, ...]
    reconciliation: CausalFoundationFrontierReconciliation
    review: CausalFoundationFrontierReviewQueue
    review_view: CausalFoundationFrontierReviewView
    summary_view: CausalFoundationFrontierSummaryView
    gate: CausalFoundationFrontierQualityGate
    bundle: CausalFoundationFrontierReleaseBundle
    release: CausalFoundationFrontierReleaseManifest
    artifacts: CausalFoundationFrontierArtifactInventory
    stages: tuple[CausalFoundationFrontierRuntimeStage, ...]
    observability: Any
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def stage_ids(self) -> tuple[str, ...]:
        return tuple(item.stage_id for item in self.stages)

    @property
    def stage_count(self) -> int:
        return len(self.stages)

    def stage(self, stage_id: str) -> CausalFoundationFrontierRuntimeStage:
        return next(item for item in self.stages if item.stage_id == stage_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"run_id": self.run_id, "fixture": self.fixture.to_dict(), "evaluation": self.evaluation.to_dict(), "metrics": self.metrics.to_dict(), "contracts": self.contracts.to_dict(), "schema": self.schema.to_dict(), "lineage": self.lineage.to_dict(), "provenance": self.provenance.to_dict(), "depth": self.depth.to_dict(), "policy": self.policy.to_dict(), "decisions": [jsonable(item) for item in self.decisions], "reconciliation": self.reconciliation.to_dict(), "review": self.review.to_dict(), "review_view": self.review_view.to_dict(), "summary_view": self.summary_view.to_dict(), "gate": self.gate.to_dict(), "bundle": self.bundle.to_dict(), "release": self.release.to_dict(), "artifacts": self.artifacts.to_dict(), "stages": [item.to_dict() for item in self.stages], "observability": self.observability.to_dict(), "accepted": self.accepted, "stage_ids": self.stage_ids, "stage_count": self.stage_count}
        if include_address:
            value["content_address"] = self.content_address
        return value


def run_causal_foundation_frontier_runtime(fixture: CausalFoundationFrontierFixture | None = None, *, run_id: str = "causal-foundation-frontier-runtime") -> CausalFoundationFrontierRuntimeReport:
    value = fixture or default_causal_foundation_frontier_fixture()
    events: list[CausalFoundationFrontierEvent] = []
    stages: list[CausalFoundationFrontierRuntimeStage] = []
    def stage(stage_id: str, sequence: int, fn: Any, detail: str) -> Any:
        result, event = record_causal_foundation_frontier_event(run_id, sequence, stage_id, fn, detail)
        events.append(event)
        address = event.output_address
        stages.append(CausalFoundationFrontierRuntimeStage(stage_id, sequence, event.state, address, detail))
        if result is None:
            raise RuntimeError(event.detail)
        return result
    audit = stage("data-audit", 1, lambda: audit_causal_foundation_frontier_data(value), "validate public aggregate boundary")
    adapters = stage("adapters", 2, build_causal_foundation_frontier_adapters, "bind four causal primitives")
    contracts = stage("contracts", 3, build_causal_foundation_frontier_contracts, "load capability contracts")
    evaluation = stage("fixture-replay", 4, lambda: evaluate_causal_foundation_frontier_fixture(value), "replay positive and control rows")
    schema = stage("schema", 5, lambda: validate_causal_foundation_frontier_schema(value, evaluation), "validate record envelope")
    metrics = stage("metrics", 6, lambda: build_causal_foundation_frontier_metrics(evaluation, value), "calculate operation metrics")
    lineage = stage("lineage", 7, lambda: build_causal_foundation_frontier_lineage(value, evaluation), "build source-to-result edges")
    provenance = stage("provenance", 8, lambda: build_causal_foundation_frontier_provenance(value, evaluation), "build content-addressed graph")
    depth = stage("depth-audit", 9, lambda: audit_causal_foundation_frontier_depth(value, evaluation, adapters, contracts, schema, metrics, lineage, provenance), "audit implementation depth")
    policy = stage("policy", 10, default_causal_foundation_frontier_policy, "apply bounded dispositions")
    decisions = stage("decisions", 11, lambda: policy.decide(evaluation), "produce row decisions")
    reconciliation = stage("reconciliation", 12, lambda: reconcile_causal_foundation_frontier(value, evaluation, decisions, policy), "reconcile expected and observed states")
    review = stage("review-queue", 13, lambda: build_causal_foundation_frontier_review_queue(evaluation, policy), "project human review queue")
    review_view = stage("review-view", 14, lambda: build_causal_foundation_frontier_review_view(value, evaluation, decisions, reconciliation, review), "build stable review table")
    summary_view = stage("summary-view", 15, lambda: build_causal_foundation_frontier_summary_view(value, metrics, review, evaluation.accepted), "build summary projection")
    gate = stage("quality-gate", 16, lambda: evaluate_causal_foundation_frontier_quality(value, evaluation, contracts, schema, metrics, lineage, reconciliation, depth, review, decisions), "run release checks")
    bundle = stage("release-bundle", 17, lambda: assemble_causal_foundation_frontier_bundle(value, evaluation, metrics, contracts, schema, lineage, provenance, depth, reconciliation, policy, review, gate, review_view, summary_view, bundle_id=run_id), "assemble release bundle")
    release = stage("release-manifest", 18, lambda: build_causal_foundation_frontier_release_manifest(bundle, gate, depth, review), "build bounded release manifest")
    artifacts = stage("artifact-inventory", 19, lambda: build_causal_foundation_frontier_artifact_inventory(value, evaluation, bundle, release, review_csv_address=review_view.content_address, summary_address=summary_view.content_address), "enumerate release artifacts")
    observability = build_causal_foundation_frontier_observability(run_id, tuple(events))
    accepted = bool(audit.accepted and evaluation.accepted and gate.accepted and bundle.publishable and release.accepted and artifacts.accepted and observability.accepted)
    return CausalFoundationFrontierRuntimeReport(run_id, value, evaluation, metrics, contracts, schema, lineage, provenance, depth, policy, decisions, reconciliation, review, review_view, summary_view, gate, bundle, release, artifacts, tuple(stages), observability, accepted)


__all__ = ["CausalFoundationFrontierRuntimeReport", "CausalFoundationFrontierRuntimeStage", "run_causal_foundation_frontier_runtime"]
