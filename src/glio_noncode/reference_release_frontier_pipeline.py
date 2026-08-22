"""End-to-end package pipeline for Domain 04 C13-C16."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .reference_release_frontier_accessibility import (
    ReferenceReleaseAccessibilityReport,
    evaluate_reference_release_accessibility,
)
from .reference_release_frontier_adapters import (
    ReferenceReleaseAdapterRegistry,
    default_reference_release_adapters,
    verify_reference_release_adapters,
)
from .reference_release_frontier_artifacts import (
    ReferenceReleaseArtifactInventory,
    build_reference_release_artifact_inventory,
    verify_reference_release_artifact_inventory,
)
from .reference_release_frontier_bundle import (
    ReferenceReleaseBundleBuilder,
    ReferenceReleaseEvidenceBundle,
    assemble_reference_release_bundle,
)
from .reference_release_frontier_checks import (
    ReferenceReleaseInvariantReport,
    run_reference_release_invariants,
)
from .reference_release_frontier_compliance import (
    ReferenceReleaseBoundaryReport,
    evaluate_reference_release_boundary,
)
from .reference_release_frontier_exports import export_reference_release_addresses
from .reference_release_frontier_observability import (
    ReferenceReleaseObservabilityReport,
    observe_reference_release,
)
from .reference_release_frontier_public_data import (
    ReferenceReleaseFixture,
    default_reference_release_fixture,
)
from .reference_release_frontier_release import (
    ReferenceReleaseManifest,
    build_reference_release_manifest,
    verify_reference_release_manifest,
)
from .reference_release_frontier_review_queue import (
    ReferenceReleaseReviewQueue,
    build_reference_release_review_queue,
    verify_reference_release_review_queue,
)
from .reference_release_frontier_runbook import (
    ReferenceReleaseRunbook,
    default_reference_release_runbook,
    verify_reference_release_runbook,
)
from .reference_release_frontier_runtime import (
    ReferenceReleaseRuntimeReport,
    run_reference_release_runtime,
)
from .reference_release_frontier_scenario_matrix import (
    ReferenceReleaseScenarioMatrix,
    build_reference_release_scenario_matrix,
    verify_reference_release_scenarios,
)
from .reference_release_frontier_thresholds import (
    ReferenceReleaseThresholdReport,
    build_reference_release_threshold_report,
    verify_reference_release_thresholds,
)
from .reference_release_frontier_validation_matrix import (
    ReferenceReleaseValidationReport,
    build_reference_release_validation_matrix,
    validate_reference_release_matrix,
)
from .reference_release_frontier_views import (
    ReferenceReleaseReviewView,
    build_reference_release_review_view,
    verify_reference_release_review_view,
)
from .serialization import content_hash, require_non_empty


@dataclass(frozen=True, slots=True)
class ReferenceReleasePipelineReport:
    """Complete package report with named addresses for every module family."""

    pipeline_id: str
    runtime: ReferenceReleaseRuntimeReport
    release: ReferenceReleaseManifest
    bundle: ReferenceReleaseEvidenceBundle
    artifacts: ReferenceReleaseArtifactInventory
    review_view: ReferenceReleaseReviewView
    review_queue: ReferenceReleaseReviewQueue
    observability: ReferenceReleaseObservabilityReport
    accessibility: ReferenceReleaseAccessibilityReport
    boundary: ReferenceReleaseBoundaryReport
    invariants: ReferenceReleaseInvariantReport
    scenarios: ReferenceReleaseScenarioMatrix
    thresholds: ReferenceReleaseThresholdReport
    validation: ReferenceReleaseValidationReport
    runbook: ReferenceReleaseRunbook
    adapters: ReferenceReleaseAdapterRegistry
    manifest: dict[str, Any]
    accepted: bool
    content_address: str

    def addresses(self) -> dict[str, str]:
        """Return the address index used by API and CLI consumers."""

        return {
            "runtime": self.runtime.content_address,
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
        return {
            "pipeline_id": self.pipeline_id,
            "runtime": self.runtime.to_dict(),
            "release": self.release.to_dict(),
            "bundle": self.bundle.to_dict(),
            "artifacts": self.artifacts.to_dict(),
            "review_view": self.review_view.to_dict(),
            "review_queue": self.review_queue.to_dict(),
            "observability": self.observability.to_dict(),
            "accessibility": self.accessibility.to_dict(),
            "boundary": self.boundary.to_dict(),
            "invariants": self.invariants.to_dict(),
            "scenarios": self.scenarios.to_dict(),
            "thresholds": self.thresholds.to_dict(),
            "validation": self.validation.to_dict(),
            "runbook": self.runbook.to_dict(),
            "adapters": self.adapters.to_dict(),
            "manifest": self.manifest,
            "accepted": self.accepted,
            "content_address": self.content_address,
            "addresses": self.addresses(),
        }


def run_reference_release_pipeline(
    fixture: ReferenceReleaseFixture | None = None,
    *,
    pipeline_id: str = "reference-release-frontier-c13-c16-pipeline",
) -> ReferenceReleasePipelineReport:
    """Run every release package layer in dependency order."""

    fixture = fixture or default_reference_release_fixture()
    require_non_empty(pipeline_id, "pipeline_id")
    runtime = run_reference_release_runtime(fixture, run_id=f"{pipeline_id}:runtime")
    release = build_reference_release_manifest(runtime, release_id=f"{pipeline_id}:release")
    bundle = assemble_reference_release_bundle(
        fixture, runtime, release, bundle_id=f"{pipeline_id}:bundle"
    )
    artifacts = build_reference_release_artifact_inventory(runtime, release, bundle)
    review_view = build_reference_release_review_view(
        fixture, runtime.evaluation, runtime.policy, release
    )
    review_queue = build_reference_release_review_queue(
        review_view, release, queue_id=f"{pipeline_id}:review"
    )
    observability = observe_reference_release(runtime)
    accessibility = evaluate_reference_release_accessibility(
        fixture, runtime.evaluation, review_view
    )
    boundary = evaluate_reference_release_boundary(
        fixture, runtime.evaluation, runtime, bundle, review_view
    )
    invariants = run_reference_release_invariants(
        fixture, runtime.evaluation, release, bundle, review_view
    )
    scenarios = build_reference_release_scenario_matrix()
    thresholds = build_reference_release_threshold_report(
        fixture, runtime.evaluation, runtime.metrics, runtime.lineage
    )
    validation = build_reference_release_validation_matrix(fixture, runtime.evaluation)
    runbook = default_reference_release_runbook()
    adapters = default_reference_release_adapters()
    manifest = export_reference_release_addresses(release)
    accepted = all(
        (
            runtime.accepted,
            release.ready,
            not verify_reference_release_manifest(release),
            bundle.accepted,
            not ReferenceReleaseBundleBuilder().verify(bundle),
            artifacts.accepted,
            not verify_reference_release_artifact_inventory(artifacts),
            review_view.accepted,
            not verify_reference_release_review_view(review_view),
            review_queue.accepted,
            not verify_reference_release_review_queue(review_queue),
            observability.accepted,
            accessibility.accepted,
            boundary.accepted,
            not boundary.failed_check_ids,
            invariants.accepted,
            scenarios.accepted,
            not verify_reference_release_scenarios(scenarios),
            thresholds.accepted,
            not verify_reference_release_thresholds(thresholds),
            validate_reference_release_matrix(validation),
            runbook.accepted,
            not verify_reference_release_runbook(runbook),
            not verify_reference_release_adapters(adapters),
        )
    )
    body = {
        "pipeline_id": pipeline_id,
        "runtime": runtime,
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
    address_body = {
        "pipeline_id": pipeline_id,
        "addresses": {
            "runtime": runtime.content_address,
            "release": release.content_address,
            "bundle": bundle.content_address,
            "artifacts": artifacts.content_address,
            "review_view": review_view.content_address,
            "review_queue": review_queue.content_address,
            "observability": observability.content_address,
            "accessibility": accessibility.content_address,
            "boundary": boundary.content_address,
            "invariants": invariants.content_address,
            "scenarios": scenarios.content_address,
            "thresholds": thresholds.content_address,
            "validation": validation.content_address,
            "runbook": runbook.content_address,
            "adapters": adapters.content_address,
        },
        "manifest": manifest,
        "accepted": accepted,
    }
    return ReferenceReleasePipelineReport(
        **body,
        content_address=content_hash(address_body, prefix="release-pipeline"),
    )


__all__ = ["ReferenceReleasePipelineReport", "run_reference_release_pipeline"]
