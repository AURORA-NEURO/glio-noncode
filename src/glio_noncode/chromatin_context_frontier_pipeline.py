"""End-to-end release pipeline for Domain 07 C01-C04."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_context_frontier_artifacts import (
    ChromatinContextFrontierArtifactInventory,
    build_chromatin_context_frontier_artifacts,
)
from .chromatin_context_frontier_bundle import (
    ChromatinContextFrontierBundle,
    build_chromatin_context_frontier_bundle,
)
from .chromatin_context_frontier_checks import (
    ChromatinContextFrontierInvariantReport,
    run_chromatin_context_frontier_invariants,
)
from .chromatin_context_frontier_compliance import (
    ChromatinContextFrontierBoundaryReport,
    evaluate_chromatin_context_frontier_boundary,
)
from .chromatin_context_frontier_exports import (
    export_chromatin_context_frontier_manifest,
    export_chromatin_context_frontier_review_csv,
)
from .chromatin_context_frontier_observability import (
    ChromatinContextFrontierObservabilityReport,
    build_chromatin_context_frontier_trace,
)
from .chromatin_context_frontier_public_data import (
    ChromatinContextFrontierFixture,
    default_chromatin_context_frontier_fixture,
)
from .chromatin_context_frontier_release import (
    ChromatinContextFrontierReleaseManifest,
    build_chromatin_context_frontier_release,
)
from .chromatin_context_frontier_replay import (
    ChromatinContextFrontierReplayReceipt,
    replay_chromatin_context_frontier,
)
from .chromatin_context_frontier_reports import (
    ChromatinContextFrontierReport,
    build_chromatin_context_frontier_report,
)
from .chromatin_context_frontier_review_queue import (
    ChromatinContextFrontierReviewQueue,
    build_chromatin_context_frontier_review_queue,
)
from .chromatin_context_frontier_runbook import (
    ChromatinContextFrontierRunbook,
    default_chromatin_context_frontier_runbook,
)
from .chromatin_context_frontier_runtime import (
    ChromatinContextFrontierRuntimeReport,
    run_chromatin_context_frontier_runtime,
)
from .chromatin_context_frontier_scenario_matrix import (
    ChromatinContextFrontierScenarioMatrix,
    build_chromatin_context_frontier_scenario_matrix,
    evaluate_chromatin_context_frontier_scenarios,
)
from .chromatin_context_frontier_source_registry import (
    ChromatinContextFrontierSourceRegistry,
    build_chromatin_context_frontier_source_registry,
)
from .chromatin_context_frontier_thresholds import (
    ChromatinContextFrontierThresholdReport,
    build_chromatin_context_frontier_threshold_report,
)
from .chromatin_context_frontier_validation_matrix import (
    ChromatinContextFrontierValidationReport,
    build_chromatin_context_frontier_validation_matrix,
    validate_chromatin_context_frontier_matrix,
)
from .chromatin_context_frontier_views import (
    ChromatinContextFrontierReviewView,
    build_chromatin_context_frontier_view,
)
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierPipelineReport:
    pipeline_id: str
    runtime: ChromatinContextFrontierRuntimeReport
    replay: ChromatinContextFrontierReplayReceipt
    release: ChromatinContextFrontierReleaseManifest
    bundle: ChromatinContextFrontierBundle
    artifacts: ChromatinContextFrontierArtifactInventory
    review_view: ChromatinContextFrontierReviewView
    review_queue: ChromatinContextFrontierReviewQueue
    observability: ChromatinContextFrontierObservabilityReport
    boundary: ChromatinContextFrontierBoundaryReport
    invariants: ChromatinContextFrontierInvariantReport
    scenarios: ChromatinContextFrontierScenarioMatrix
    thresholds: ChromatinContextFrontierThresholdReport
    validation: ChromatinContextFrontierValidationReport
    runbook: ChromatinContextFrontierRunbook
    source_registry: ChromatinContextFrontierSourceRegistry
    report: ChromatinContextFrontierReport
    manifest: dict[str, Any]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.pipeline_id:
            raise ValidationError("pipeline ID is required")
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


def run_chromatin_context_frontier_pipeline(
    fixture: ChromatinContextFrontierFixture | None = None,
    *,
    pipeline_id: str = "chromatin-context-frontier-d07-c01-c04",
) -> ChromatinContextFrontierPipelineReport:
    selected = fixture or default_chromatin_context_frontier_fixture()
    if not pipeline_id:
        raise ValidationError("pipeline ID is required")
    runtime = run_chromatin_context_frontier_runtime(fixture=selected)
    replay = replay_chromatin_context_frontier(selected, replay_id=f"{pipeline_id}:replay")
    release = build_chromatin_context_frontier_release(runtime)
    bundle = build_chromatin_context_frontier_bundle(selected, runtime.evaluation, release)
    artifacts = build_chromatin_context_frontier_artifacts(runtime.quality, release, bundle)
    view = build_chromatin_context_frontier_view(
        selected, runtime.evaluation, runtime.policy, release
    )
    queue = build_chromatin_context_frontier_review_queue(
        view, release, queue_id=f"{pipeline_id}:review"
    )
    observability = build_chromatin_context_frontier_trace(runtime)
    boundary = evaluate_chromatin_context_frontier_boundary(selected, runtime.evaluation)
    invariants = run_chromatin_context_frontier_invariants(selected, runtime.evaluation)
    scenarios = evaluate_chromatin_context_frontier_scenarios(
        build_chromatin_context_frontier_scenario_matrix()
    )
    thresholds = build_chromatin_context_frontier_threshold_report()
    validation = build_chromatin_context_frontier_validation_matrix()
    runbook = default_chromatin_context_frontier_runbook()
    source_registry = build_chromatin_context_frontier_source_registry(selected)
    report = build_chromatin_context_frontier_report(
        selected, runtime.evaluation, runtime.metrics, view
    )
    review_csv = export_chromatin_context_frontier_review_csv(view)
    manifest = export_chromatin_context_frontier_manifest(report, csv_text=review_csv)
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
            boundary.accepted,
            invariants.accepted,
            scenarios.accepted,
            thresholds.accepted,
            validate_chromatin_context_frontier_matrix(validation),
            runbook.accepted,
            source_registry.accepted,
            report.accepted,
        )
    )
    return ChromatinContextFrontierPipelineReport(
        pipeline_id,
        runtime,
        replay,
        release,
        bundle,
        artifacts,
        view,
        queue,
        observability,
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


__all__ = [
    "ChromatinContextFrontierPipelineReport",
    "run_chromatin_context_frontier_pipeline",
]
