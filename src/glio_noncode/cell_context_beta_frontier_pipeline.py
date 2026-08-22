"""End-to-end composition for Domain 08 C05-C08."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_beta_frontier_accessibility import (
    CellContextBetaFrontierAccessibilityReport,
    evaluate_cell_context_beta_frontier_accessibility,
)
from .cell_context_beta_frontier_artifacts import (
    CellContextBetaFrontierArtifactInventory,
    build_cell_context_beta_frontier_artifacts,
)
from .cell_context_beta_frontier_bundle import (
    CellContextBetaFrontierBundle,
    build_cell_context_beta_frontier_bundle,
)
from .cell_context_beta_frontier_compliance import (
    CellContextBetaFrontierBoundaryReport,
    evaluate_cell_context_beta_frontier_boundary,
)
from .cell_context_beta_frontier_contracts import (
    CellContextBetaFrontierContractReport,
    build_cell_context_beta_frontier_contracts,
)
from .cell_context_beta_frontier_depth import (
    CellContextBetaFrontierDepthReport,
    audit_cell_context_beta_frontier_depth,
)
from .cell_context_beta_frontier_fixture_eval import (
    CellContextBetaFrontierEvaluation,
    evaluate_cell_context_beta_frontier_fixture,
)
from .cell_context_beta_frontier_gate_depth import (
    CellContextBetaFrontierGateDepthReport,
    audit_cell_context_beta_frontier_gates,
)
from .cell_context_beta_frontier_integrity import (
    CellContextBetaFrontierIntegrityReport,
    evaluate_cell_context_beta_frontier_integrity,
)
from .cell_context_beta_frontier_lineage import (
    CellContextBetaFrontierLineage,
    build_cell_context_beta_frontier_lineage,
)
from .cell_context_beta_frontier_metrics import (
    CellContextBetaFrontierMetrics,
    build_cell_context_beta_frontier_metrics,
)
from .cell_context_beta_frontier_observability import (
    CellContextBetaFrontierObservabilityReport,
    build_cell_context_beta_frontier_trace,
)
from .cell_context_beta_frontier_policy import (
    CellContextBetaFrontierPolicyReport,
    evaluate_cell_context_beta_frontier_policy,
)
from .cell_context_beta_frontier_public_data import (
    CellContextBetaFrontierDataAudit,
    CellContextBetaFrontierFixture,
    audit_cell_context_beta_frontier_data,
    default_cell_context_beta_frontier_fixture,
)
from .cell_context_beta_frontier_quality_gate import (
    CellContextBetaFrontierQualityReport,
    build_cell_context_beta_frontier_quality,
)
from .cell_context_beta_frontier_reconciliation import (
    CellContextBetaFrontierReconciliation,
    reconcile_cell_context_beta_frontier,
)
from .cell_context_beta_frontier_release import (
    CellContextBetaFrontierReleaseManifest,
    build_cell_context_beta_frontier_release,
)
from .cell_context_beta_frontier_review_queue import (
    CellContextBetaFrontierReviewQueue,
    build_cell_context_beta_frontier_review_queue,
)
from .cell_context_beta_frontier_schema import (
    CellContextBetaFrontierSchemaReport,
    validate_cell_context_beta_frontier_schema,
)
from .cell_context_beta_frontier_source_registry import (
    CellContextBetaFrontierSourceRegistry,
    build_cell_context_beta_frontier_source_registry,
)
from .cell_context_beta_frontier_validation_matrix import (
    CellContextBetaFrontierValidationReport,
    build_cell_context_beta_frontier_validation_matrix,
)
from .cell_context_beta_frontier_views import (
    CellContextBetaFrontierReviewView,
    build_cell_context_beta_frontier_view,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierStage:
    stage_id: str
    status: str
    input_count: int
    output_count: int
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierPipelineReport:
    run_id: str
    fixture: CellContextBetaFrontierFixture
    data: CellContextBetaFrontierDataAudit
    contracts: CellContextBetaFrontierContractReport
    sources: CellContextBetaFrontierSourceRegistry
    evaluation: CellContextBetaFrontierEvaluation
    schema: CellContextBetaFrontierSchemaReport
    metrics: CellContextBetaFrontierMetrics
    lineage: CellContextBetaFrontierLineage
    policy: CellContextBetaFrontierPolicyReport
    reconciliation: CellContextBetaFrontierReconciliation
    quality: CellContextBetaFrontierQualityReport
    boundary: CellContextBetaFrontierBoundaryReport
    integrity: CellContextBetaFrontierIntegrityReport
    depth: CellContextBetaFrontierDepthReport
    gates: CellContextBetaFrontierGateDepthReport
    validation: CellContextBetaFrontierValidationReport
    accessibility: CellContextBetaFrontierAccessibilityReport
    review_queue: CellContextBetaFrontierReviewQueue
    view: CellContextBetaFrontierReviewView
    release: CellContextBetaFrontierReleaseManifest
    bundle: CellContextBetaFrontierBundle
    artifacts: CellContextBetaFrontierArtifactInventory
    trace: CellContextBetaFrontierObservabilityReport
    stages: tuple[CellContextBetaFrontierStage, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.run_id or not self.stages:
            raise ValueError("beta pipeline report is incomplete")
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
            "gates": self.gates.to_dict(),
            "validation": self.validation.to_dict(),
            "accessibility": self.accessibility.to_dict(),
            "review_queue": self.review_queue.to_dict(),
            "view": self.view.to_dict(),
            "release": self.release.to_dict(),
            "bundle": self.bundle.to_dict(),
            "artifacts": self.artifacts.to_dict(),
            "trace": self.trace.to_dict(),
            "stages": [item.to_dict() for item in self.stages],
            "failed_stages": list(self.failed_stages),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def _stage(
    stage_id: str, passed: bool, inputs: int, outputs: int, detail: str
) -> CellContextBetaFrontierStage:
    return CellContextBetaFrontierStage(
        stage_id, "passed" if passed else "failed", inputs, outputs, detail
    )


def run_cell_context_beta_frontier_pipeline(
    fixture: CellContextBetaFrontierFixture | None = None,
    run_id: str = "cell-context-beta-frontier",
) -> CellContextBetaFrontierPipelineReport:
    fixture = fixture or default_cell_context_beta_frontier_fixture()
    data = audit_cell_context_beta_frontier_data(fixture)
    contracts = build_cell_context_beta_frontier_contracts(fixture.evidence_boundary)
    sources = build_cell_context_beta_frontier_source_registry(fixture)
    evaluation = evaluate_cell_context_beta_frontier_fixture(fixture)
    schema = validate_cell_context_beta_frontier_schema(fixture, evaluation)
    metrics = build_cell_context_beta_frontier_metrics(evaluation)
    lineage = build_cell_context_beta_frontier_lineage(fixture, evaluation)
    policy = evaluate_cell_context_beta_frontier_policy(evaluation)
    reconciliation = reconcile_cell_context_beta_frontier(evaluation)
    quality = build_cell_context_beta_frontier_quality(
        fixture, data, schema, evaluation, reconciliation
    )
    boundary = evaluate_cell_context_beta_frontier_boundary(fixture)
    integrity = evaluate_cell_context_beta_frontier_integrity(fixture, evaluation)
    depth = audit_cell_context_beta_frontier_depth(fixture, evaluation)
    gates = audit_cell_context_beta_frontier_gates(evaluation)
    validation = build_cell_context_beta_frontier_validation_matrix(evaluation)
    accessibility = evaluate_cell_context_beta_frontier_accessibility(evaluation)
    review_queue = build_cell_context_beta_frontier_review_queue(evaluation)
    view = build_cell_context_beta_frontier_view(evaluation)
    release = build_cell_context_beta_frontier_release(fixture, evaluation, quality)
    bundle = build_cell_context_beta_frontier_bundle(
        fixture, release, metrics, lineage, policy, depth, gates
    )
    artifacts = build_cell_context_beta_frontier_artifacts(bundle, evaluation)
    trace = build_cell_context_beta_frontier_trace(evaluation, run_id)
    stages = (
        _stage("load", data.accepted, 1, len(fixture.records), "public aggregate fixture loaded"),
        _stage(
            "contracts",
            contracts.accepted,
            4,
            contracts.unique_operations,
            "four operation contracts checked",
        ),
        _stage(
            "sources",
            sources.accepted,
            len(fixture.sources),
            len(sources.entries),
            "source receipt index built",
        ),
        _stage(
            "execute",
            evaluation.accepted,
            len(fixture.records),
            len(evaluation.records),
            "positive and control rows executed",
        ),
        _stage(
            "schema",
            schema.accepted,
            len(fixture.records),
            len(schema.checks),
            "schema and boundary checks run",
        ),
        _stage(
            "metrics",
            metrics.accepted,
            len(evaluation.records),
            len(metrics.metrics),
            "bounded metrics calculated",
        ),
        _stage(
            "lineage",
            lineage.accepted,
            len(evaluation.records),
            len(lineage.edges),
            "source lineage assembled",
        ),
        _stage(
            "policy",
            policy.accepted,
            len(evaluation.records),
            len(policy.decisions),
            "review policy evaluated",
        ),
        _stage(
            "reconcile",
            reconciliation.accepted,
            len(evaluation.records),
            len(reconciliation.items),
            "expected rows reconciled",
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
            depth.accepted and gates.accepted,
            len(depth.dimensions) + len(gates.gates),
            sum(item.passed for item in depth.dimensions)
            + sum(item.supported_count > 0 for item in gates.gates),
            "depth and gate audits evaluated",
        ),
        _stage(
            "release",
            release.publishable
            and boundary.accepted
            and integrity.accepted
            and validation.accepted,
            4,
            1,
            "bounded release policy evaluated",
        ),
    )
    accepted = (
        all(item.status == "passed" for item in stages)
        and accessibility.accepted
        and artifacts.accepted
    )
    return CellContextBetaFrontierPipelineReport(
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
        gates,
        validation,
        accessibility,
        review_queue,
        view,
        release,
        bundle,
        artifacts,
        trace,
        stages,
        accepted,
    )


__all__ = [
    "CellContextBetaFrontierPipelineReport",
    "CellContextBetaFrontierStage",
    "run_cell_context_beta_frontier_pipeline",
]
