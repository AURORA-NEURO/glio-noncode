"""Twelve-stage release pipeline for Domain 09 C01-C04."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_context_frontier_accessibility import (
    TopologyContextFrontierAccessibilityReport,
    evaluate_topology_context_frontier_accessibility,
)
from .topology_context_frontier_artifacts import (
    TopologyContextFrontierArtifactInventory,
    build_topology_context_frontier_artifacts,
)
from .topology_context_frontier_bundle import (
    TopologyContextFrontierBundle,
    build_topology_context_frontier_bundle,
)
from .topology_context_frontier_candidate_depth import (
    TopologyContextFrontierCandidateDepthReport,
    audit_topology_context_frontier_candidates,
)
from .topology_context_frontier_checks import (
    TopologyContextFrontierInvariantReport,
    run_topology_context_frontier_invariants,
)
from .topology_context_frontier_compliance import (
    TopologyContextFrontierBoundaryReport,
    evaluate_topology_context_frontier_boundary,
)
from .topology_context_frontier_contracts import (
    TopologyContextFrontierContractReport,
    build_topology_context_frontier_contracts,
)
from .topology_context_frontier_delta_depth import (
    TopologyContextFrontierDeltaDepthReport,
    audit_topology_context_frontier_deltas,
)
from .topology_context_frontier_depth import (
    TopologyContextFrontierDepthReport,
    audit_topology_context_frontier_depth,
)
from .topology_context_frontier_fixture_eval import (
    TopologyContextFrontierEvaluation,
    evaluate_topology_context_frontier_fixture,
)
from .topology_context_frontier_integrity import (
    TopologyContextFrontierIntegrityReport,
    evaluate_topology_context_frontier_integrity,
)
from .topology_context_frontier_lineage import (
    TopologyContextFrontierLineage,
    build_topology_context_frontier_lineage,
)
from .topology_context_frontier_metrics import (
    TopologyContextFrontierMetrics,
    build_topology_context_frontier_metrics,
)
from .topology_context_frontier_observability import (
    TopologyContextFrontierObservabilityReport,
    build_topology_context_frontier_trace,
)
from .topology_context_frontier_policy import (
    TopologyContextFrontierPolicyReport,
    evaluate_topology_context_frontier_policy,
)
from .topology_context_frontier_provenance import (
    TopologyContextFrontierProvenanceGraph,
    build_topology_context_frontier_provenance,
)
from .topology_context_frontier_public_data import (
    TopologyContextFrontierDataAudit,
    TopologyContextFrontierFixture,
    audit_topology_context_frontier_data,
    default_topology_context_frontier_fixture,
)
from .topology_context_frontier_quality_gate import (
    TopologyContextFrontierQualityReport,
    build_topology_context_frontier_quality,
)
from .topology_context_frontier_reconciliation import (
    TopologyContextFrontierReconciliation,
    reconcile_topology_context_frontier,
)
from .topology_context_frontier_release import (
    TopologyContextFrontierReleaseManifest,
    build_topology_context_frontier_release,
)
from .topology_context_frontier_review_queue import (
    TopologyContextFrontierReviewQueue,
    build_topology_context_frontier_review_queue,
)
from .topology_context_frontier_scenario_matrix import (
    TopologyContextFrontierScenarioMatrix,
    build_topology_context_frontier_scenario_matrix,
)
from .topology_context_frontier_schema import (
    TopologyContextFrontierSchemaReport,
    validate_topology_context_frontier_schema,
)
from .topology_context_frontier_source_registry import (
    TopologyContextFrontierSourceRegistry,
    build_topology_context_frontier_source_registry,
)
from .topology_context_frontier_validation_matrix import (
    TopologyContextFrontierValidationReport,
    build_topology_context_frontier_validation_matrix,
)
from .topology_context_frontier_views import (
    TopologyContextFrontierReviewView,
    build_topology_context_frontier_view,
)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierStage:
    stage_id: str
    status: str
    input_count: int
    output_count: int
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierPipelineReport:
    run_id: str
    fixture: TopologyContextFrontierFixture
    data: TopologyContextFrontierDataAudit
    contracts: TopologyContextFrontierContractReport
    sources: TopologyContextFrontierSourceRegistry
    evaluation: TopologyContextFrontierEvaluation
    schema: TopologyContextFrontierSchemaReport
    metrics: TopologyContextFrontierMetrics
    lineage: TopologyContextFrontierLineage
    provenance: TopologyContextFrontierProvenanceGraph
    policy: TopologyContextFrontierPolicyReport
    reconciliation: TopologyContextFrontierReconciliation
    quality: TopologyContextFrontierQualityReport
    boundary: TopologyContextFrontierBoundaryReport
    integrity: TopologyContextFrontierIntegrityReport
    depth: TopologyContextFrontierDepthReport
    candidates: TopologyContextFrontierCandidateDepthReport
    deltas: TopologyContextFrontierDeltaDepthReport
    validation: TopologyContextFrontierValidationReport
    scenarios: TopologyContextFrontierScenarioMatrix
    accessibility: TopologyContextFrontierAccessibilityReport
    review_queue: TopologyContextFrontierReviewQueue
    view: TopologyContextFrontierReviewView
    release: TopologyContextFrontierReleaseManifest
    bundle: TopologyContextFrontierBundle
    artifacts: TopologyContextFrontierArtifactInventory
    trace: TopologyContextFrontierObservabilityReport
    invariants: TopologyContextFrontierInvariantReport
    stages: tuple[TopologyContextFrontierStage, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "run_id": self.run_id,
                        "fixture": self.fixture.content_address,
                        "stages": self.stages,
                        "accepted": self.accepted,
                    }
                ),
            )

    @property
    def failed_stages(self) -> tuple[str, ...]:
        return tuple(item.stage_id for item in self.stages if item.status != "passed")

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "fixture": self.fixture.to_dict(False),
            "data": self.data.to_dict(),
            "contracts": self.contracts.to_dict(),
            "sources": self.sources.to_dict(),
            "evaluation": self.evaluation.to_dict(),
            "schema": self.schema.to_dict(),
            "metrics": self.metrics.to_dict(),
            "lineage": self.lineage.to_dict(),
            "provenance": self.provenance.to_dict(),
            "policy": self.policy.to_dict(),
            "reconciliation": self.reconciliation.to_dict(),
            "quality": self.quality.to_dict(),
            "boundary": self.boundary.to_dict(),
            "integrity": self.integrity.to_dict(),
            "depth": self.depth.to_dict(),
            "candidates": self.candidates.to_dict(),
            "deltas": self.deltas.to_dict(),
            "validation": self.validation.to_dict(),
            "scenarios": self.scenarios.to_dict(),
            "accessibility": self.accessibility.to_dict(),
            "review_queue": self.review_queue.to_dict(),
            "view": self.view.to_dict(),
            "release": self.release.to_dict(),
            "bundle": self.bundle.to_dict(),
            "artifacts": self.artifacts.to_dict(),
            "trace": self.trace.to_dict(),
            "invariants": self.invariants.to_dict(),
            "stages": [item.to_dict() for item in self.stages],
            "failed_stages": self.failed_stages,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def _stage(
    stage_id: str, passed: bool, input_count: int, output_count: int, detail: str
) -> TopologyContextFrontierStage:
    return TopologyContextFrontierStage(
        stage_id, "passed" if passed else "failed", input_count, output_count, detail
    )


def run_topology_context_frontier_pipeline(
    fixture: TopologyContextFrontierFixture | None = None,
    *,
    run_id: str = "topology-context-frontier-run",
) -> TopologyContextFrontierPipelineReport:
    value = fixture or default_topology_context_frontier_fixture()
    data = audit_topology_context_frontier_data(value)
    contracts = build_topology_context_frontier_contracts()
    sources = build_topology_context_frontier_source_registry(value)
    evaluation = evaluate_topology_context_frontier_fixture(value)
    schema = validate_topology_context_frontier_schema(value, evaluation)
    metrics = build_topology_context_frontier_metrics(evaluation)
    lineage = build_topology_context_frontier_lineage(value, evaluation)
    provenance = build_topology_context_frontier_provenance(value, evaluation)
    policy = evaluate_topology_context_frontier_policy(evaluation)
    reconciliation = reconcile_topology_context_frontier(evaluation)
    quality = build_topology_context_frontier_quality(
        value, data, schema, evaluation, reconciliation
    )
    boundary = evaluate_topology_context_frontier_boundary(value, evaluation)
    integrity = evaluate_topology_context_frontier_integrity(value, evaluation)
    depth = audit_topology_context_frontier_depth(value, evaluation)
    candidates = audit_topology_context_frontier_candidates(evaluation)
    deltas = audit_topology_context_frontier_deltas(evaluation)
    validation = build_topology_context_frontier_validation_matrix(evaluation)
    scenarios = build_topology_context_frontier_scenario_matrix(evaluation)
    accessibility = evaluate_topology_context_frontier_accessibility(evaluation)
    review_queue = build_topology_context_frontier_review_queue(evaluation)
    view = build_topology_context_frontier_view(evaluation)
    release = build_topology_context_frontier_release(value, evaluation, quality)
    bundle = build_topology_context_frontier_bundle(value, release, metrics, deltas)
    artifacts = build_topology_context_frontier_artifacts(bundle, evaluation)
    trace = build_topology_context_frontier_trace(evaluation, run_id)
    invariants = run_topology_context_frontier_invariants(value, evaluation)
    stages = (
        _stage("fixture", data.accepted, 16, len(value.records), "fixture and aggregate boundary"),
        _stage(
            "contracts",
            contracts.accepted,
            4,
            len(contracts.contracts),
            "typed operation contracts",
        ),
        _stage(
            "sources",
            sources.accepted,
            len(value.sources),
            len(sources.entries),
            "source receipt closure",
        ),
        _stage(
            "evaluation",
            evaluation.accepted,
            len(value.records),
            len(evaluation.rows),
            "positive and control replay",
        ),
        _stage(
            "schema", schema.accepted, len(evaluation.rows), len(schema.checks), "schema checks"
        ),
        _stage(
            "quality", quality.accepted, len(schema.checks), len(quality.checks), "quality floor"
        ),
        _stage(
            "policy",
            policy.accepted and provenance.accepted,
            len(evaluation.rows),
            len(policy.decisions),
            "review policy and provenance",
        ),
        _stage(
            "boundary",
            boundary.accepted,
            len(value.records),
            len(boundary.checks),
            "aggregate boundary",
        ),
        _stage(
            "depth",
            depth.accepted and candidates.accepted and deltas.accepted,
            len(evaluation.rows),
            len(depth.dimensions) + len(candidates.observations) + len(deltas.observations),
            "depth, candidate, and delta audits",
        ),
        _stage(
            "validation",
            validation.accepted and scenarios.accepted,
            len(evaluation.rows),
            len(validation.cells) + len(scenarios.scenarios),
            "matrix and scenarios",
        ),
        _stage(
            "integrity",
            integrity.accepted and accessibility.accepted and invariants.accepted,
            len(evaluation.rows),
            len(integrity.checks) + len(accessibility.operations) + len(invariants.results),
            "integrity and accessibility",
        ),
        _stage(
            "release",
            release.publishable and bundle.accepted and artifacts.accepted,
            len(bundle.members),
            len(artifacts.artifacts),
            "release bundle and inventory",
        ),
    )
    accepted = (
        all(item.status == "passed" for item in stages)
        and lineage.accepted
        and provenance.accepted
        and reconciliation.accepted
        and view.accepted
        and trace.accepted
    )
    return TopologyContextFrontierPipelineReport(
        run_id,
        value,
        data,
        contracts,
        sources,
        evaluation,
        schema,
        metrics,
        lineage,
        provenance,
        policy,
        reconciliation,
        quality,
        boundary,
        integrity,
        depth,
        candidates,
        deltas,
        validation,
        scenarios,
        accessibility,
        review_queue,
        view,
        release,
        bundle,
        artifacts,
        trace,
        invariants,
        stages,
        accepted,
    )


__all__ = [
    "TopologyContextFrontierPipelineReport",
    "TopologyContextFrontierStage",
    "run_topology_context_frontier_pipeline",
]
