"""Twelve-stage end-to-end pipeline for Domain 08 C09-C12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_alpha_frontier_accessibility import (
    CellContextAlphaFrontierAccessibilityReport,
    evaluate_cell_context_alpha_frontier_accessibility,
)
from .cell_context_alpha_frontier_artifacts import (
    CellContextAlphaFrontierArtifactInventory,
    build_cell_context_alpha_frontier_artifacts,
)
from .cell_context_alpha_frontier_bundle import (
    CellContextAlphaFrontierBundle,
    build_cell_context_alpha_frontier_bundle,
)
from .cell_context_alpha_frontier_candidate_depth import (
    CellContextAlphaFrontierCandidateDepthReport,
    audit_cell_context_alpha_frontier_candidates,
)
from .cell_context_alpha_frontier_checks import (
    CellContextAlphaFrontierInvariantReport,
    run_cell_context_alpha_frontier_invariants,
)
from .cell_context_alpha_frontier_compliance import (
    CellContextAlphaFrontierBoundaryReport,
    evaluate_cell_context_alpha_frontier_boundary,
)
from .cell_context_alpha_frontier_contracts import (
    CellContextAlphaFrontierContractReport,
    build_cell_context_alpha_frontier_contracts,
)
from .cell_context_alpha_frontier_delta_depth import (
    CellContextAlphaFrontierDeltaDepthReport,
    audit_cell_context_alpha_frontier_deltas,
)
from .cell_context_alpha_frontier_depth import (
    CellContextAlphaFrontierDepthReport,
    audit_cell_context_alpha_frontier_depth,
)
from .cell_context_alpha_frontier_fixture_eval import (
    CellContextAlphaFrontierEvaluation,
    evaluate_cell_context_alpha_frontier_fixture,
)
from .cell_context_alpha_frontier_integrity import (
    CellContextAlphaFrontierIntegrityReport,
    evaluate_cell_context_alpha_frontier_integrity,
)
from .cell_context_alpha_frontier_lineage import (
    CellContextAlphaFrontierLineage,
    build_cell_context_alpha_frontier_lineage,
)
from .cell_context_alpha_frontier_metrics import (
    CellContextAlphaFrontierMetrics,
    build_cell_context_alpha_frontier_metrics,
)
from .cell_context_alpha_frontier_observability import (
    CellContextAlphaFrontierObservabilityReport,
    build_cell_context_alpha_frontier_trace,
)
from .cell_context_alpha_frontier_policy import (
    CellContextAlphaFrontierPolicyReport,
    evaluate_cell_context_alpha_frontier_policy,
)
from .cell_context_alpha_frontier_public_data import (
    CellContextAlphaFrontierDataAudit,
    CellContextAlphaFrontierFixture,
    audit_cell_context_alpha_frontier_data,
    default_cell_context_alpha_frontier_fixture,
)
from .cell_context_alpha_frontier_quality_gate import (
    CellContextAlphaFrontierQualityReport,
    build_cell_context_alpha_frontier_quality,
)
from .cell_context_alpha_frontier_reconciliation import (
    CellContextAlphaFrontierReconciliation,
    reconcile_cell_context_alpha_frontier,
)
from .cell_context_alpha_frontier_release import (
    CellContextAlphaFrontierReleaseManifest,
    build_cell_context_alpha_frontier_release,
)
from .cell_context_alpha_frontier_review_queue import (
    CellContextAlphaFrontierReviewQueue,
    build_cell_context_alpha_frontier_review_queue,
)
from .cell_context_alpha_frontier_schema import (
    CellContextAlphaFrontierSchemaReport,
    validate_cell_context_alpha_frontier_schema,
)
from .cell_context_alpha_frontier_source_registry import (
    CellContextAlphaFrontierSourceRegistry,
    build_cell_context_alpha_frontier_source_registry,
)
from .cell_context_alpha_frontier_validation_matrix import (
    CellContextAlphaFrontierValidationReport,
    build_cell_context_alpha_frontier_validation_matrix,
)
from .cell_context_alpha_frontier_views import (
    CellContextAlphaFrontierReviewView,
    build_cell_context_alpha_frontier_view,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierStage:
    stage_id: str
    status: str
    input_count: int
    output_count: int
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierPipelineReport:
    run_id: str
    fixture: CellContextAlphaFrontierFixture
    data: CellContextAlphaFrontierDataAudit
    contracts: CellContextAlphaFrontierContractReport
    sources: CellContextAlphaFrontierSourceRegistry
    evaluation: CellContextAlphaFrontierEvaluation
    schema: CellContextAlphaFrontierSchemaReport
    metrics: CellContextAlphaFrontierMetrics
    lineage: CellContextAlphaFrontierLineage
    policy: CellContextAlphaFrontierPolicyReport
    reconciliation: CellContextAlphaFrontierReconciliation
    quality: CellContextAlphaFrontierQualityReport
    boundary: CellContextAlphaFrontierBoundaryReport
    integrity: CellContextAlphaFrontierIntegrityReport
    depth: CellContextAlphaFrontierDepthReport
    candidates: CellContextAlphaFrontierCandidateDepthReport
    deltas: CellContextAlphaFrontierDeltaDepthReport
    validation: CellContextAlphaFrontierValidationReport
    accessibility: CellContextAlphaFrontierAccessibilityReport
    review_queue: CellContextAlphaFrontierReviewQueue
    view: CellContextAlphaFrontierReviewView
    release: CellContextAlphaFrontierReleaseManifest
    bundle: CellContextAlphaFrontierBundle
    artifacts: CellContextAlphaFrontierArtifactInventory
    trace: CellContextAlphaFrontierObservabilityReport
    invariants: CellContextAlphaFrontierInvariantReport
    stages: tuple[CellContextAlphaFrontierStage, ...]
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
            "policy": self.policy.to_dict(),
            "reconciliation": self.reconciliation.to_dict(),
            "quality": self.quality.to_dict(),
            "boundary": self.boundary.to_dict(),
            "integrity": self.integrity.to_dict(),
            "depth": self.depth.to_dict(),
            "candidates": self.candidates.to_dict(),
            "deltas": self.deltas.to_dict(),
            "validation": self.validation.to_dict(),
            "accessibility": self.accessibility.to_dict(),
            "review_queue": self.review_queue.to_dict(),
            "view": self.view.to_dict(),
            "release": self.release.to_dict(),
            "bundle": self.bundle.to_dict(),
            "artifacts": self.artifacts.to_dict(),
            "trace": self.trace.to_dict(),
            "invariants": self.invariants.to_dict(),
            "stages": [item.to_dict() for item in self.stages],
            "failed_stages": list(self.failed_stages),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def _stage(
    stage_id: str, passed: bool, inputs: int, outputs: int, detail: str
) -> CellContextAlphaFrontierStage:
    return CellContextAlphaFrontierStage(
        stage_id, "passed" if passed else "failed", inputs, outputs, detail
    )


def run_cell_context_alpha_frontier_pipeline(
    fixture: CellContextAlphaFrontierFixture | None = None,
    run_id: str = "cell-context-alpha-frontier",
) -> CellContextAlphaFrontierPipelineReport:
    fixture = fixture or default_cell_context_alpha_frontier_fixture()
    data = audit_cell_context_alpha_frontier_data(fixture)
    contracts = build_cell_context_alpha_frontier_contracts(fixture.evidence_boundary)
    sources = build_cell_context_alpha_frontier_source_registry(fixture)
    evaluation = evaluate_cell_context_alpha_frontier_fixture(fixture)
    schema = validate_cell_context_alpha_frontier_schema(fixture, evaluation)
    metrics = build_cell_context_alpha_frontier_metrics(evaluation)
    lineage = build_cell_context_alpha_frontier_lineage(fixture, evaluation)
    policy = evaluate_cell_context_alpha_frontier_policy(evaluation)
    reconciliation = reconcile_cell_context_alpha_frontier(evaluation)
    quality = build_cell_context_alpha_frontier_quality(
        fixture, data, schema, evaluation, reconciliation
    )
    boundary = evaluate_cell_context_alpha_frontier_boundary(fixture)
    integrity = evaluate_cell_context_alpha_frontier_integrity(fixture, evaluation)
    depth = audit_cell_context_alpha_frontier_depth(fixture, evaluation)
    candidates = audit_cell_context_alpha_frontier_candidates(evaluation)
    deltas = audit_cell_context_alpha_frontier_deltas(evaluation)
    validation = build_cell_context_alpha_frontier_validation_matrix(evaluation)
    accessibility = evaluate_cell_context_alpha_frontier_accessibility(evaluation)
    review_queue = build_cell_context_alpha_frontier_review_queue(evaluation)
    view = build_cell_context_alpha_frontier_view(evaluation)
    release = build_cell_context_alpha_frontier_release(fixture, evaluation, quality)
    bundle = build_cell_context_alpha_frontier_bundle(
        fixture, release, metrics, lineage, depth, candidates, deltas
    )
    artifacts = build_cell_context_alpha_frontier_artifacts(bundle, evaluation)
    trace = build_cell_context_alpha_frontier_trace(evaluation, run_id)
    invariants = run_cell_context_alpha_frontier_invariants(fixture, evaluation)
    stages = (
        _stage("load", data.accepted, 1, len(fixture.records), "aggregate fixture loaded"),
        _stage(
            "contracts",
            contracts.accepted,
            4,
            contracts.unique_operations,
            "four alpha contracts checked",
        ),
        _stage("sources", sources.accepted, 4, len(sources.entries), "source registry built"),
        _stage(
            "execute", evaluation.accepted, 16, len(evaluation.records), "alpha priors executed"
        ),
        _stage("schema", schema.accepted, 16, len(schema.checks), "schema checks run"),
        _stage("metrics", metrics.accepted, 16, len(metrics.metrics), "metrics calculated"),
        _stage("lineage", lineage.accepted, 16, len(lineage.edges), "lineage assembled"),
        _stage("policy", policy.accepted, 16, len(policy.decisions), "policy evaluated"),
        _stage(
            "reconcile", reconciliation.accepted, 16, len(reconciliation.items), "rows reconciled"
        ),
        _stage(
            "quality",
            quality.accepted,
            len(quality.checks),
            quality.passed_count,
            "quality gate evaluated",
        ),
        _stage(
            "depth",
            depth.accepted and candidates.accepted and deltas.accepted,
            len(depth.dimensions) + candidates.candidate_count + len(deltas.observations),
            sum(item.passed for item in depth.dimensions)
            + candidates.candidate_count
            + len(deltas.observations),
            "candidate and delta depth evaluated",
        ),
        _stage(
            "release",
            release.publishable
            and boundary.accepted
            and integrity.accepted
            and validation.accepted
            and invariants.accepted,
            5,
            1,
            "bounded release evaluated",
        ),
    )
    accepted = (
        all(item.status == "passed" for item in stages)
        and accessibility.accepted
        and artifacts.accepted
    )
    return CellContextAlphaFrontierPipelineReport(
        run_id,
        fixture,
        data,
        contracts,
        sources,
        evaluation,
        schema,
        metrics,
        lineage,
        policy,
        reconciliation,
        quality,
        boundary,
        integrity,
        depth,
        candidates,
        deltas,
        validation,
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
    "CellContextAlphaFrontierPipelineReport",
    "CellContextAlphaFrontierStage",
    "run_cell_context_alpha_frontier_pipeline",
]
