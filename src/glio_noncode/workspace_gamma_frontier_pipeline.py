"""End-to-end release rehearsal that exercises every C09-C12 package module."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workspace_gamma_frontier_accessibility import (
    GammaFrontierAccessibilityReport,
    evaluate_gamma_frontier_accessibility,
)
from .workspace_gamma_frontier_adapters import (
    GammaFrontierAdapterRegistry,
    default_gamma_frontier_adapters,
)
from .workspace_gamma_frontier_artifacts import (
    GammaFrontierArtifactInventory,
    build_gamma_frontier_artifact_inventory,
)
from .workspace_gamma_frontier_bundle import (
    GammaFrontierEvidenceBundle,
    assemble_gamma_frontier_bundle,
)
from .workspace_gamma_frontier_checks import (
    GammaFrontierInvariantReport,
    run_gamma_frontier_invariants,
)
from .workspace_gamma_frontier_compliance import (
    GammaFrontierBoundaryReport,
    evaluate_gamma_frontier_boundary,
)
from .workspace_gamma_frontier_exports import export_gamma_frontier_manifest
from .workspace_gamma_frontier_observability import (
    GammaFrontierObservabilityReport,
    observe_gamma_frontier,
)
from .workspace_gamma_frontier_public_data import (
    GammaFrontierFixture,
    default_gamma_frontier_fixture,
)
from .workspace_gamma_frontier_release import (
    GammaFrontierReleaseManifest,
    build_gamma_frontier_release_manifest,
)
from .workspace_gamma_frontier_replay import GammaFrontierReplayReceipt, replay_gamma_frontier
from .workspace_gamma_frontier_review_queue import (
    GammaFrontierReviewQueue,
    build_gamma_frontier_review_queue,
)
from .workspace_gamma_frontier_runbook import GammaFrontierRunbook, default_gamma_frontier_runbook
from .workspace_gamma_frontier_runtime import GammaFrontierRuntimeReport, run_gamma_frontier_runtime
from .workspace_gamma_frontier_scenario_matrix import (
    GammaFrontierScenarioMatrix,
    build_gamma_frontier_scenario_matrix,
)
from .workspace_gamma_frontier_thresholds import (
    GammaFrontierThresholdReport,
    build_gamma_frontier_threshold_report,
)
from .workspace_gamma_frontier_validation_matrix import (
    GammaFrontierValidationReport,
    build_gamma_frontier_validation_matrix,
    validate_gamma_frontier_matrix,
)
from .workspace_gamma_frontier_views import (
    GammaFrontierReviewView,
    build_gamma_frontier_review_view,
)


@dataclass(frozen=True, slots=True)
class GammaFrontierPipelineReport:
    """Complete package report with named addresses for every module family."""

    pipeline_id: str
    runtime: GammaFrontierRuntimeReport
    replay: GammaFrontierReplayReceipt
    release: GammaFrontierReleaseManifest
    bundle: GammaFrontierEvidenceBundle
    artifacts: GammaFrontierArtifactInventory
    review_view: GammaFrontierReviewView
    review_queue: GammaFrontierReviewQueue
    observability: GammaFrontierObservabilityReport
    accessibility: GammaFrontierAccessibilityReport
    boundary: GammaFrontierBoundaryReport
    invariants: GammaFrontierInvariantReport
    scenarios: GammaFrontierScenarioMatrix
    thresholds: GammaFrontierThresholdReport
    validation: GammaFrontierValidationReport
    runbook: GammaFrontierRunbook
    adapters: GammaFrontierAdapterRegistry
    manifest: dict[str, Any]
    accepted: bool
    content_address: str

    def addresses(self) -> dict[str, str]:
        """Return the package address index used by API consumers."""

        return {
            "runtime": self.runtime.content_address,
            "replay": self.replay.content_address,
            "release": self.release.content_address,
            "bundle": self.bundle.content_address,
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
            "adapters": self.adapters.content_address,
        }

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"addresses": self.addresses()}


def run_gamma_frontier_pipeline(
    fixture: GammaFrontierFixture | None = None,
    *,
    pipeline_id: str = "workspace-gamma-frontier-c09-c12-pipeline",
) -> GammaFrontierPipelineReport:
    """Run every package layer in dependency order and return one report."""

    fixture = fixture or default_gamma_frontier_fixture()
    require_non_empty(pipeline_id, "pipeline_id")
    runtime = run_gamma_frontier_runtime(fixture, run_id=f"{pipeline_id}:runtime")
    replay = replay_gamma_frontier(fixture, replay_id=f"{pipeline_id}:replay")
    release = build_gamma_frontier_release_manifest(
        runtime, replay, release_id=f"{pipeline_id}:release"
    )
    bundle = assemble_gamma_frontier_bundle(
        fixture, runtime, release, bundle_id=f"{pipeline_id}:bundle"
    )
    artifacts = build_gamma_frontier_artifact_inventory(runtime, bundle, release)
    review_view = build_gamma_frontier_review_view(
        fixture, runtime.evaluation, runtime.policy_decisions, release
    )
    review_queue = build_gamma_frontier_review_queue(
        review_view, release, queue_id=f"{pipeline_id}:review"
    )
    observability = observe_gamma_frontier(runtime)
    accessibility = evaluate_gamma_frontier_accessibility(fixture, runtime.evaluation)
    boundary = evaluate_gamma_frontier_boundary(fixture, runtime.evaluation)
    invariants = run_gamma_frontier_invariants(fixture, runtime.evaluation)
    scenarios = build_gamma_frontier_scenario_matrix()
    thresholds = build_gamma_frontier_threshold_report()
    validation = build_gamma_frontier_validation_matrix()
    runbook = default_gamma_frontier_runbook()
    adapters = default_gamma_frontier_adapters()
    manifest = export_gamma_frontier_manifest(runtime.metrics, bundle, release)
    accepted = all(
        (
            runtime.accepted,
            replay.accepted,
            release.state.value == "ready",
            bundle.accepted,
            artifacts.accepted,
            review_queue.accepted,
            accessibility.accepted,
            boundary.accepted,
            invariants.accepted,
            thresholds.accepted,
            validate_gamma_frontier_matrix(validation),
        )
    )
    body = {
        "pipeline_id": pipeline_id,
        "runtime": runtime,
        "replay": replay,
        "release": release,
        "bundle": bundle,
        "artifacts": artifacts,
        "review_view": review_view,
        "review_queue": review_queue,
        "observability": observability,
        "accessibility": accessibility,
        "boundary": boundary,
        "invariants": invariants,
        "scenarios": scenarios,
        "thresholds": thresholds,
        "validation": validation,
        "runbook": runbook,
        "adapters": adapters,
        "manifest": manifest,
        "accepted": accepted,
    }
    return GammaFrontierPipelineReport(
        **body, content_address=content_hash(body, prefix="pipeline")
    )


__all__ = ["GammaFrontierPipelineReport", "run_gamma_frontier_pipeline"]
