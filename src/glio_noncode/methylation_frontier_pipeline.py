"""End-to-end rehearsal for all Domain 07 C05-C08 package layers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .methylation_frontier_accessibility import (
    MethylationFrontierAccessibilityReport,
    evaluate_methylation_frontier_accessibility,
)
from .methylation_frontier_artifacts import (
    MethylationFrontierArtifactInventory,
    build_methylation_frontier_artifacts,
)
from .methylation_frontier_checks import (
    MethylationFrontierInvariantReport,
    run_methylation_frontier_invariants,
)
from .methylation_frontier_compliance import (
    MethylationFrontierBoundaryReport,
    evaluate_methylation_frontier_boundary,
)
from .methylation_frontier_exports import (
    export_methylation_frontier_manifest,
    export_methylation_frontier_review_rows,
)
from .methylation_frontier_observability import (
    MethylationFrontierObservabilityReport,
    observe_methylation_frontier,
)
from .methylation_frontier_public_data import (
    MethylationFrontierFixture,
    default_methylation_frontier_fixture,
)
from .methylation_frontier_release import (
    MethylationFrontierReleaseManifest,
    build_methylation_frontier_release,
)
from .methylation_frontier_replay import (
    MethylationFrontierReplayReceipt,
    replay_methylation_frontier,
)
from .methylation_frontier_reports import (
    MethylationFrontierReport,
    build_methylation_frontier_report,
)
from .methylation_frontier_review_queue import (
    MethylationFrontierReviewQueue,
    build_methylation_frontier_review_queue,
)
from .methylation_frontier_runbook import (
    MethylationFrontierRunbook,
    default_methylation_frontier_runbook,
)
from .methylation_frontier_runtime import (
    MethylationFrontierRuntimeReport,
    run_methylation_frontier_runtime,
)
from .methylation_frontier_scenario_matrix import (
    MethylationFrontierScenarioMatrix,
    build_methylation_frontier_scenario_matrix,
)
from .methylation_frontier_source_registry import (
    MethylationFrontierSourceRegistry,
    build_methylation_frontier_source_registry,
)
from .methylation_frontier_thresholds import (
    MethylationFrontierThresholdReport,
    build_methylation_frontier_threshold_report,
)
from .methylation_frontier_validation_matrix import (
    MethylationFrontierValidationReport,
    build_methylation_frontier_validation_matrix,
    validate_methylation_frontier_matrix,
)
from .methylation_frontier_views import (
    MethylationFrontierReviewView,
    build_methylation_frontier_review_view,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class MethylationFrontierPipelineReport:
    pipeline_id: str
    runtime: MethylationFrontierRuntimeReport
    replay: MethylationFrontierReplayReceipt
    release: MethylationFrontierReleaseManifest
    bundle: Any
    artifacts: MethylationFrontierArtifactInventory
    review_view: MethylationFrontierReviewView
    review_queue: MethylationFrontierReviewQueue
    observability: MethylationFrontierObservabilityReport
    accessibility: MethylationFrontierAccessibilityReport
    boundary: MethylationFrontierBoundaryReport
    invariants: MethylationFrontierInvariantReport
    scenarios: MethylationFrontierScenarioMatrix
    thresholds: MethylationFrontierThresholdReport
    validation: MethylationFrontierValidationReport
    runbook: MethylationFrontierRunbook
    source_registry: MethylationFrontierSourceRegistry
    report: MethylationFrontierReport
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


def run_methylation_frontier_pipeline(
    fixture: MethylationFrontierFixture | None = None,
    *,
    pipeline_id: str = "methylation-frontier-d07-c05-c08",
) -> MethylationFrontierPipelineReport:
    """Run each package layer in dependency order and return one report."""

    fixture = fixture or default_methylation_frontier_fixture()
    if not pipeline_id:
        raise ValidationError("pipeline ID is required")
    runtime = run_methylation_frontier_runtime(fixture=fixture, options=None)
    replay = replay_methylation_frontier(fixture, replay_id=f"{pipeline_id}:replay")
    release = build_methylation_frontier_release(runtime)
    from .methylation_frontier_bundle import build_methylation_frontier_bundle

    bundle = build_methylation_frontier_bundle(fixture, runtime.evaluation, release)
    artifacts = build_methylation_frontier_artifacts(runtime.quality, release, bundle)
    view = build_methylation_frontier_review_view(
        fixture, runtime.evaluation, runtime.policy, release
    )
    queue = build_methylation_frontier_review_queue(view, release, queue_id=f"{pipeline_id}:review")
    observability = observe_methylation_frontier(runtime)
    accessibility = evaluate_methylation_frontier_accessibility(fixture, runtime.evaluation)
    boundary = evaluate_methylation_frontier_boundary(fixture, runtime.evaluation)
    invariants = run_methylation_frontier_invariants(fixture, runtime.evaluation)
    scenarios = build_methylation_frontier_scenario_matrix()
    thresholds = build_methylation_frontier_threshold_report()
    validation = build_methylation_frontier_validation_matrix()
    runbook = default_methylation_frontier_runbook()
    source_registry = build_methylation_frontier_source_registry(fixture)
    report = build_methylation_frontier_report(fixture, runtime.evaluation, runtime.metrics, view)
    review_csv = export_methylation_frontier_review_rows(view)
    manifest = export_methylation_frontier_manifest(report, csv_text=review_csv)
    accepted = all(
        (
            runtime.accepted,
            replay.accepted,
            release.accepted,
            bundle.accepted,
            artifacts.accepted,
            queue.accepted,
            observability.accepted,
            accessibility.accepted,
            boundary.accepted,
            invariants.accepted,
            scenarios.accepted,
            thresholds.accepted,
            validate_methylation_frontier_matrix(validation),
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
    return MethylationFrontierPipelineReport(**body)


__all__ = ["MethylationFrontierPipelineReport", "run_methylation_frontier_pipeline"]
