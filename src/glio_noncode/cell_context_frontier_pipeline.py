"""End-to-end release pipeline for Domain 08 C01-C04."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_frontier_accessibility import (
    CellContextFrontierAccessibilityReport,
    evaluate_cell_context_frontier_accessibility,
)
from .cell_context_frontier_artifacts import (
    CellContextFrontierArtifactInventory,
    build_cell_context_frontier_artifacts,
)
from .cell_context_frontier_bundle import (
    CellContextFrontierBundle,
    build_cell_context_frontier_bundle,
)
from .cell_context_frontier_checks import (
    CellContextFrontierInvariantReport,
    run_cell_context_frontier_invariants,
)
from .cell_context_frontier_compliance import (
    CellContextFrontierBoundaryReport,
    evaluate_cell_context_frontier_boundary,
)
from .cell_context_frontier_depth import (
    CellContextFrontierDepthReport,
    audit_cell_context_frontier_depth,
)
from .cell_context_frontier_exports import (
    export_cell_context_frontier_manifest,
    export_cell_context_frontier_review_csv,
)
from .cell_context_frontier_integrity import (
    CellContextFrontierIntegrityReport,
    evaluate_cell_context_frontier_integrity,
)
from .cell_context_frontier_observability import (
    CellContextFrontierObservabilityReport,
    build_cell_context_frontier_trace,
)
from .cell_context_frontier_public_data import (
    CellContextFrontierFixture,
    default_cell_context_frontier_fixture,
)
from .cell_context_frontier_release import (
    CellContextFrontierReleaseManifest,
    build_cell_context_frontier_release,
)
from .cell_context_frontier_replay import (
    CellContextFrontierReplayReceipt,
    replay_cell_context_frontier,
)
from .cell_context_frontier_reports import (
    CellContextFrontierReport,
    build_cell_context_frontier_report,
)
from .cell_context_frontier_review_queue import (
    CellContextFrontierReviewQueue,
    build_cell_context_frontier_review_queue,
)
from .cell_context_frontier_runbook import (
    CellContextFrontierRunbook,
    default_cell_context_frontier_runbook,
)
from .cell_context_frontier_runtime import (
    CellContextFrontierRuntimeReport,
    run_cell_context_frontier_runtime,
)
from .cell_context_frontier_scenario_matrix import (
    CellContextFrontierScenarioMatrix,
    build_cell_context_frontier_scenario_matrix,
    evaluate_cell_context_frontier_scenarios,
)
from .cell_context_frontier_source_registry import (
    CellContextFrontierSourceRegistry,
    build_cell_context_frontier_source_registry,
)
from .cell_context_frontier_thresholds import (
    CellContextFrontierThresholdReport,
    build_cell_context_frontier_threshold_report,
)
from .cell_context_frontier_validation_matrix import (
    CellContextFrontierValidationReport,
    build_cell_context_frontier_validation_matrix,
    validate_cell_context_frontier_matrix,
)
from .cell_context_frontier_views import (
    CellContextFrontierReviewView,
    build_cell_context_frontier_view,
)
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextFrontierPipelineReport:
    pipeline_id: str
    runtime: CellContextFrontierRuntimeReport
    replay: CellContextFrontierReplayReceipt
    release: CellContextFrontierReleaseManifest
    bundle: CellContextFrontierBundle
    artifacts: CellContextFrontierArtifactInventory
    review_view: CellContextFrontierReviewView
    review_queue: CellContextFrontierReviewQueue
    observability: CellContextFrontierObservabilityReport
    accessibility: CellContextFrontierAccessibilityReport
    depth: CellContextFrontierDepthReport
    integrity: CellContextFrontierIntegrityReport
    boundary: CellContextFrontierBoundaryReport
    invariants: CellContextFrontierInvariantReport
    scenarios: CellContextFrontierScenarioMatrix
    thresholds: CellContextFrontierThresholdReport
    validation: CellContextFrontierValidationReport
    runbook: CellContextFrontierRunbook
    source_registry: CellContextFrontierSourceRegistry
    report: CellContextFrontierReport
    manifest: dict[str, Any]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.pipeline_id:
            raise ValidationError("cell pipeline ID is required")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.addresses()))

    def addresses(self) -> dict[str, str]:
        return {
            "runtime": self.runtime.content_address,
            "replay": self.replay.content_address,
            "release": self.release.content_address,
            "bundle": self.bundle.root_address,
            "artifacts": self.artifacts.content_address,
            "review_view": self.review_view.content_address,
            "review_queue": self.review_queue.content_address,
            "observability": self.observability.content_address,
            "accessibility": self.accessibility.content_address,
            "depth": self.depth.content_address,
            "integrity": self.integrity.content_address,
            "boundary": self.boundary.content_address,
            "invariants": self.invariants.content_address,
            "scenarios": self.scenarios.content_address,
            "thresholds": self.thresholds.content_address,
            "validation": self.validation.content_address,
            "runbook": self.runbook.content_address,
            "source_registry": self.source_registry.content_address,
            "report": self.report.content_address,
        }

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"addresses": self.addresses()}


def run_cell_context_frontier_pipeline(
    fixture: CellContextFrontierFixture | None = None,
    *,
    pipeline_id: str = "cell-context-frontier-d08-c01-c04",
) -> CellContextFrontierPipelineReport:
    selected = fixture or default_cell_context_frontier_fixture()
    runtime = run_cell_context_frontier_runtime(fixture=selected)
    replay = replay_cell_context_frontier(selected, replay_id=f"{pipeline_id}:replay")
    release = build_cell_context_frontier_release(runtime)
    bundle = build_cell_context_frontier_bundle(selected, runtime.evaluation, release)
    artifacts = build_cell_context_frontier_artifacts(runtime.quality, release, bundle)
    view = build_cell_context_frontier_view(selected, runtime.evaluation, runtime.policy, release)
    queue = build_cell_context_frontier_review_queue(
        view, release, queue_id=f"{pipeline_id}:review"
    )
    observability = build_cell_context_frontier_trace(runtime)
    accessibility = evaluate_cell_context_frontier_accessibility(runtime.evaluation)
    depth = audit_cell_context_frontier_depth(runtime.evaluation)
    integrity = evaluate_cell_context_frontier_integrity(selected, runtime.evaluation)
    boundary = evaluate_cell_context_frontier_boundary(selected, runtime.evaluation)
    invariants = run_cell_context_frontier_invariants(selected, runtime.evaluation)
    scenarios = evaluate_cell_context_frontier_scenarios(
        build_cell_context_frontier_scenario_matrix()
    )
    thresholds = build_cell_context_frontier_threshold_report()
    validation = build_cell_context_frontier_validation_matrix()
    runbook = default_cell_context_frontier_runbook()
    source_registry = build_cell_context_frontier_source_registry(selected)
    report = build_cell_context_frontier_report(selected, runtime.evaluation, runtime.metrics, view)
    review_csv = export_cell_context_frontier_review_csv(view)
    manifest = export_cell_context_frontier_manifest(report, csv_text=review_csv)
    accepted = all(
        (
            runtime.accepted,
            replay.accepted,
            release.accepted,
            bundle.accepted,
            artifacts.accepted,
            view.accepted,
            queue.accepted,
            observability.accepted,
            accessibility.accepted,
            depth.accepted,
            integrity.accepted,
            boundary.accepted,
            invariants.accepted,
            scenarios.accepted,
            thresholds.accepted,
            validate_cell_context_frontier_matrix(validation),
            runbook.accepted,
            source_registry.accepted,
            report.accepted,
        )
    )
    return CellContextFrontierPipelineReport(
        pipeline_id,
        runtime,
        replay,
        release,
        bundle,
        artifacts,
        view,
        queue,
        observability,
        accessibility,
        depth,
        integrity,
        boundary,
        invariants,
        scenarios,
        thresholds,
        validation,
        runbook,
        source_registry,
        report,
        manifest,
        accepted,
    )


__all__ = ["CellContextFrontierPipelineReport", "run_cell_context_frontier_pipeline"]
