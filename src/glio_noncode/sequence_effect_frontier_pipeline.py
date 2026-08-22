"""End-to-end aggregate report for Domain 06 C01–C04."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sequence_effect_frontier_accessibility import (
    SequenceEffectAccessibilityReport,
    audit_sequence_effect_accessibility,
)
from .sequence_effect_frontier_adapters import (
    SequenceEffectAdapterRegistry,
    build_sequence_effect_adapters,
)
from .sequence_effect_frontier_artifacts import (
    SequenceEffectArtifactInventory,
    build_sequence_effect_artifacts,
)
from .sequence_effect_frontier_bundle import SequenceEffectBundle, build_sequence_effect_bundle
from .sequence_effect_frontier_checks import (
    SequenceEffectInvariantReport,
    run_sequence_effect_invariants,
)
from .sequence_effect_frontier_compliance import (
    SequenceEffectBoundaryReport,
    audit_sequence_effect_boundary,
)
from .sequence_effect_frontier_fixture_eval import (
    SequenceEffectEvaluation,
    evaluate_sequence_effect_fixture,
)
from .sequence_effect_frontier_public_data import (
    SequenceEffectFixture,
    default_sequence_effect_fixture,
)
from .sequence_effect_frontier_release import (
    SequenceEffectReleaseManifest,
    build_sequence_effect_release,
)
from .sequence_effect_frontier_review_queue import (
    SequenceEffectReviewQueue,
    build_sequence_effect_review_queue,
)
from .sequence_effect_frontier_runbook import SequenceEffectRunbook, default_sequence_effect_runbook
from .sequence_effect_frontier_runtime import (
    SequenceEffectRuntimeOptions,
    SequenceEffectRuntimeReport,
    run_sequence_effect_pipeline,
)
from .sequence_effect_frontier_scenario_matrix import (
    SequenceEffectScenarioReport,
    evaluate_sequence_effect_scenarios,
)
from .sequence_effect_frontier_thresholds import (
    SequenceEffectThresholdReport,
    build_sequence_effect_threshold_report,
)
from .sequence_effect_frontier_validation_matrix import (
    SequenceEffectValidationReport,
    build_sequence_effect_validation_matrix,
)
from .sequence_effect_frontier_views import SequenceEffectView, build_sequence_effect_view
from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class SequenceEffectPipelineReport:
    fixture: SequenceEffectFixture
    evaluation: SequenceEffectEvaluation
    runtime: SequenceEffectRuntimeReport
    release: SequenceEffectReleaseManifest
    bundle: SequenceEffectBundle
    artifacts: SequenceEffectArtifactInventory
    view: SequenceEffectView
    review_queue: SequenceEffectReviewQueue
    adapters: SequenceEffectAdapterRegistry
    accessibility: SequenceEffectAccessibilityReport
    boundary: SequenceEffectBoundaryReport
    invariants: SequenceEffectInvariantReport
    scenarios: SequenceEffectScenarioReport
    thresholds: SequenceEffectThresholdReport
    validation: SequenceEffectValidationReport
    runbook: SequenceEffectRunbook
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "fixture": self.fixture.content_address,
                        "evaluation": self.evaluation.content_address,
                        "runtime": self.runtime.content_address,
                        "release": self.release.content_address,
                        "bundle": self.bundle.content_address,
                        "artifacts": self.artifacts.content_address,
                        "view": self.view.content_address,
                        "queue": self.review_queue.content_address,
                        "adapters": self.adapters.content_address,
                        "accessibility": self.accessibility.content_address,
                        "boundary": self.boundary.content_address,
                        "invariants": self.invariants.content_address,
                        "scenarios": self.scenarios.content_address,
                        "thresholds": self.thresholds.content_address,
                        "validation": self.validation.content_address,
                        "runbook": self.runbook.content_address,
                        "accepted": self.accepted,
                    }
                ),
            )

    def addresses(self) -> tuple[str, ...]:
        return (
            self.fixture.content_address,
            self.evaluation.content_address,
            self.runtime.content_address,
            self.release.content_address,
            self.bundle.content_address,
            self.artifacts.content_address,
            self.view.content_address,
            self.review_queue.content_address,
            self.adapters.content_address,
            self.accessibility.content_address,
            self.boundary.content_address,
            self.invariants.content_address,
            self.scenarios.content_address,
            self.thresholds.content_address,
            self.validation.content_address,
            self.runbook.content_address,
            self.content_address,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "content_address": self.content_address,
            "fixture": self.fixture.to_dict(),
            "evaluation": {
                "accepted": self.evaluation.accepted,
                "content_address": self.evaluation.content_address,
                "check_count": len(self.evaluation.checks),
            },
            "runtime": self.runtime.to_dict(),
            "release": self.release.to_dict(),
            "bundle": self.bundle.to_dict(),
            "artifacts": self.artifacts.to_dict(),
            "view": self.view.to_dict(),
            "review_queue": self.review_queue.to_dict(),
            "adapters": self.adapters.to_dict(),
            "accessibility": self.accessibility.to_dict(),
            "boundary": self.boundary.to_dict(),
            "invariants": self.invariants.to_dict(),
            "scenarios": self.scenarios.to_dict(),
            "thresholds": self.thresholds.to_dict(),
            "validation": self.validation.to_dict(),
            "runbook": self.runbook.to_dict(),
        }


def run_sequence_effect_frontier_pipeline(
    fixture: SequenceEffectFixture | None = None, *, run_id: str = "sequence-effect-pipeline"
) -> SequenceEffectPipelineReport:
    fixture = fixture or default_sequence_effect_fixture()
    evaluation = evaluate_sequence_effect_fixture(fixture)
    runtime = run_sequence_effect_pipeline(
        SequenceEffectRuntimeOptions(run_id=run_id), fixture=fixture
    )
    release = build_sequence_effect_release(runtime.quality, runtime)
    view = build_sequence_effect_view(fixture, evaluation)
    bundle = build_sequence_effect_bundle(fixture, evaluation, release)
    artifacts = build_sequence_effect_artifacts(runtime.quality, release, bundle)
    queue = build_sequence_effect_review_queue(view)
    adapters = build_sequence_effect_adapters()
    accessibility = audit_sequence_effect_accessibility(fixture, view)
    boundary = audit_sequence_effect_boundary(fixture, runtime)
    invariants = run_sequence_effect_invariants(fixture, evaluation)
    scenarios = evaluate_sequence_effect_scenarios(fixture, evaluation)
    thresholds = build_sequence_effect_threshold_report()
    validation = build_sequence_effect_validation_matrix(fixture, evaluation)
    runbook = default_sequence_effect_runbook()
    accepted = all(
        (
            evaluation.accepted,
            runtime.accepted,
            release.accepted,
            bundle.accepted,
            artifacts.accepted,
            view.accepted,
            queue.accepted,
            adapters.accepted,
            accessibility.accepted,
            boundary.accepted,
            invariants.accepted,
            scenarios.accepted,
            thresholds.accepted,
            validation.accepted,
        )
    )
    return SequenceEffectPipelineReport(
        fixture,
        evaluation,
        runtime,
        release,
        bundle,
        artifacts,
        view,
        queue,
        adapters,
        accessibility,
        boundary,
        invariants,
        scenarios,
        thresholds,
        validation,
        runbook,
        accepted,
    )


__all__ = ["SequenceEffectPipelineReport", "run_sequence_effect_frontier_pipeline"]
