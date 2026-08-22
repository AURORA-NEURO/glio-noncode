"""End-to-end pipeline for Domain 07 C09-C12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_alpha_frontier_accessibility import (
    ChromatinAlphaFrontierAccessibilityReport,
    evaluate_chromatin_alpha_frontier_accessibility,
)
from .chromatin_alpha_frontier_artifacts import (
    ChromatinAlphaFrontierArtifactInventory,
    build_chromatin_alpha_frontier_artifacts,
)
from .chromatin_alpha_frontier_bundle import (
    ChromatinAlphaFrontierBundle,
    build_chromatin_alpha_frontier_bundle,
)
from .chromatin_alpha_frontier_checks import (
    ChromatinAlphaFrontierInvariantReport,
    run_chromatin_alpha_frontier_invariants,
)
from .chromatin_alpha_frontier_compliance import (
    ChromatinAlphaFrontierBoundaryReport,
    evaluate_chromatin_alpha_frontier_boundary,
)
from .chromatin_alpha_frontier_exports import (
    export_chromatin_alpha_frontier_manifest,
    export_chromatin_alpha_frontier_review_csv,
)
from .chromatin_alpha_frontier_observability import (
    ChromatinAlphaFrontierObservabilityReport,
    build_chromatin_alpha_frontier_trace,
)
from .chromatin_alpha_frontier_public_data import (
    ChromatinAlphaFrontierFixture,
    default_chromatin_alpha_frontier_fixture,
)
from .chromatin_alpha_frontier_release import (
    ChromatinAlphaFrontierReleaseManifest,
    build_chromatin_alpha_frontier_release,
)
from .chromatin_alpha_frontier_replay import (
    ChromatinAlphaFrontierReplayReceipt,
    replay_chromatin_alpha_frontier,
)
from .chromatin_alpha_frontier_reports import (
    ChromatinAlphaFrontierReport,
    build_chromatin_alpha_frontier_report,
)
from .chromatin_alpha_frontier_review_queue import (
    ChromatinAlphaFrontierReviewQueue,
    build_chromatin_alpha_frontier_review_queue,
)
from .chromatin_alpha_frontier_runbook import (
    ChromatinAlphaFrontierRunbook,
    default_chromatin_alpha_frontier_runbook,
)
from .chromatin_alpha_frontier_runtime import (
    ChromatinAlphaFrontierRuntimeReport,
    run_chromatin_alpha_frontier_runtime,
)
from .chromatin_alpha_frontier_scenario_matrix import (
    ChromatinAlphaFrontierScenarioMatrix,
    build_chromatin_alpha_frontier_scenario_matrix,
    evaluate_chromatin_alpha_frontier_scenarios,
)
from .chromatin_alpha_frontier_source_registry import (
    ChromatinAlphaFrontierSourceRegistry,
    build_chromatin_alpha_frontier_source_registry,
)
from .chromatin_alpha_frontier_thresholds import (
    ChromatinAlphaFrontierThresholdReport,
    build_chromatin_alpha_frontier_threshold_report,
)
from .chromatin_alpha_frontier_validation_matrix import (
    ChromatinAlphaFrontierValidationReport,
    build_chromatin_alpha_frontier_validation_matrix,
    validate_chromatin_alpha_frontier_matrix,
)
from .chromatin_alpha_frontier_views import (
    ChromatinAlphaFrontierReviewView,
    build_chromatin_alpha_frontier_view,
)
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierPipelineReport:
    pipeline_id: str
    runtime: ChromatinAlphaFrontierRuntimeReport
    replay: ChromatinAlphaFrontierReplayReceipt
    release: ChromatinAlphaFrontierReleaseManifest
    bundle: ChromatinAlphaFrontierBundle
    artifacts: ChromatinAlphaFrontierArtifactInventory
    review_view: ChromatinAlphaFrontierReviewView
    review_queue: ChromatinAlphaFrontierReviewQueue
    observability: ChromatinAlphaFrontierObservabilityReport
    accessibility: ChromatinAlphaFrontierAccessibilityReport
    boundary: ChromatinAlphaFrontierBoundaryReport
    invariants: ChromatinAlphaFrontierInvariantReport
    scenarios: ChromatinAlphaFrontierScenarioMatrix
    thresholds: ChromatinAlphaFrontierThresholdReport
    validation: ChromatinAlphaFrontierValidationReport
    runbook: ChromatinAlphaFrontierRunbook
    source_registry: ChromatinAlphaFrontierSourceRegistry
    report: ChromatinAlphaFrontierReport
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
            "accessibility": self.accessibility.content_address,
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


def run_chromatin_alpha_frontier_pipeline(
    fixture: ChromatinAlphaFrontierFixture | None = None,
    *,
    pipeline_id: str = "chromatin-alpha-frontier-d07-c09-c12",
) -> ChromatinAlphaFrontierPipelineReport:
    selected = fixture or default_chromatin_alpha_frontier_fixture()
    if not pipeline_id:
        raise ValidationError("pipeline ID is required")
    runtime = run_chromatin_alpha_frontier_runtime(fixture=selected)
    replay = replay_chromatin_alpha_frontier(selected, replay_id=f"{pipeline_id}:replay")
    release = build_chromatin_alpha_frontier_release(runtime)
    bundle = build_chromatin_alpha_frontier_bundle(selected, runtime.evaluation, release)
    artifacts = build_chromatin_alpha_frontier_artifacts(runtime.quality, release, bundle)
    view = build_chromatin_alpha_frontier_view(
        selected, runtime.evaluation, runtime.policy, release
    )
    queue = build_chromatin_alpha_frontier_review_queue(
        view, release, queue_id=f"{pipeline_id}:review"
    )
    observability = build_chromatin_alpha_frontier_trace(runtime)
    accessibility = evaluate_chromatin_alpha_frontier_accessibility(selected, runtime.evaluation)
    boundary = evaluate_chromatin_alpha_frontier_boundary(selected, runtime.evaluation)
    invariants = run_chromatin_alpha_frontier_invariants(selected, runtime.evaluation)
    scenarios = evaluate_chromatin_alpha_frontier_scenarios(
        build_chromatin_alpha_frontier_scenario_matrix()
    )
    thresholds = build_chromatin_alpha_frontier_threshold_report()
    validation = build_chromatin_alpha_frontier_validation_matrix()
    runbook = default_chromatin_alpha_frontier_runbook()
    source_registry = build_chromatin_alpha_frontier_source_registry(selected)
    report = build_chromatin_alpha_frontier_report(
        selected, runtime.evaluation, runtime.metrics, view
    )
    review_csv = export_chromatin_alpha_frontier_review_csv(view)
    manifest = export_chromatin_alpha_frontier_manifest(report, csv_text=review_csv)
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
            boundary.accepted,
            invariants.accepted,
            scenarios.accepted,
            thresholds.accepted,
            validate_chromatin_alpha_frontier_matrix(validation),
            runbook is not None,
            source_registry.accepted,
            report.accepted,
        )
    )
    body = {
        "pipeline_id": pipeline_id,
        "runtime": runtime,
        "replay": replay,
        "release": release,
        "bundle": bundle,
        "artifacts": artifacts,
        "review_view": view,
        "review_queue": queue,
        "observability": observability,
        "accessibility": accessibility,
        "boundary": boundary,
        "invariants": invariants,
        "scenarios": scenarios,
        "thresholds": thresholds,
        "validation": validation,
        "runbook": runbook,
        "source_registry": source_registry,
        "report": report,
        "manifest": manifest,
        "accepted": accepted,
    }
    return ChromatinAlphaFrontierPipelineReport(**body)


__all__ = ["ChromatinAlphaFrontierPipelineReport", "run_chromatin_alpha_frontier_pipeline"]
