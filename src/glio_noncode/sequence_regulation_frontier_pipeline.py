"""End-to-end aggregate evidence plane for Domain 06 C09-C12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sequence_regulation_frontier_accessibility import (
    SequenceRegulationAccessibilityReport,
    audit_sequence_regulation_accessibility,
)
from .sequence_regulation_frontier_artifacts import (
    SequenceRegulationArtifactInventory,
    build_sequence_regulation_artifacts,
)
from .sequence_regulation_frontier_bundle import (
    SequenceRegulationBundle,
    build_sequence_regulation_bundle,
)
from .sequence_regulation_frontier_checks import (
    SequenceRegulationInvariantReport,
    run_sequence_regulation_invariants,
)
from .sequence_regulation_frontier_compliance import (
    SequenceRegulationBoundaryReport,
    audit_sequence_regulation_boundary,
)
from .sequence_regulation_frontier_fixture_eval import SequenceRegulationEvaluation
from .sequence_regulation_frontier_observability import (
    SequenceRegulationTrace,
    build_sequence_regulation_trace,
)
from .sequence_regulation_frontier_public_data import (
    SequenceRegulationFixture,
    default_sequence_regulation_fixture,
)
from .sequence_regulation_frontier_release import (
    SequenceRegulationReleaseManifest,
    build_sequence_regulation_release,
)
from .sequence_regulation_frontier_replay import (
    SequenceRegulationReplayReport,
    replay_sequence_regulation_evaluation,
)
from .sequence_regulation_frontier_review_queue import (
    SequenceRegulationReviewQueue,
    build_sequence_regulation_review_queue,
)
from .sequence_regulation_frontier_runbook import (
    SequenceRegulationRunbook,
    default_sequence_regulation_runbook,
)
from .sequence_regulation_frontier_runtime import (
    SequenceRegulationRuntimeOptions,
    SequenceRegulationRuntimeReport,
    run_sequence_regulation_runtime,
)
from .sequence_regulation_frontier_scenario_matrix import (
    SequenceRegulationScenarioReport,
    evaluate_sequence_regulation_scenarios,
)
from .sequence_regulation_frontier_thresholds import (
    SequenceRegulationThresholdReport,
    build_sequence_regulation_threshold_report,
)
from .sequence_regulation_frontier_validation_matrix import (
    SequenceRegulationValidationReport,
    build_sequence_regulation_validation_matrix,
)
from .sequence_regulation_frontier_views import (
    SequenceRegulationView,
    build_sequence_regulation_view,
)
from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class SequenceRegulationPipelineReport:
    fixture: SequenceRegulationFixture
    runtime: SequenceRegulationRuntimeReport
    release: SequenceRegulationReleaseManifest
    bundle: SequenceRegulationBundle
    artifacts: SequenceRegulationArtifactInventory
    view: SequenceRegulationView
    queue: SequenceRegulationReviewQueue
    trace: SequenceRegulationTrace
    accessibility: SequenceRegulationAccessibilityReport
    boundary: SequenceRegulationBoundaryReport
    invariants: SequenceRegulationInvariantReport
    scenarios: SequenceRegulationScenarioReport
    thresholds: SequenceRegulationThresholdReport
    validation: SequenceRegulationValidationReport
    replay: SequenceRegulationReplayReport
    runbook: SequenceRegulationRunbook
    accepted: bool
    content_address: str = ""

    @property
    def evaluation(self) -> SequenceRegulationEvaluation:
        return self.runtime.evaluation

    @property
    def data(self):
        return self.runtime.data

    @property
    def contracts(self):
        return self.runtime.contracts

    @property
    def adapters(self):
        return self.runtime.adapters

    @property
    def schema(self):
        return self.runtime.schema

    @property
    def metrics(self):
        return self.runtime.metrics

    @property
    def lineage(self):
        return self.runtime.lineage

    @property
    def policy(self):
        return self.runtime.policy

    @property
    def quality(self):
        return self.runtime.quality

    @property
    def reconciliation(self):
        return self.runtime.reconciliation

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "fixture": self.fixture.content_address,
                        "runtime": self.runtime.content_address,
                        "release": self.release.content_address,
                        "bundle": self.bundle.root_address,
                        "artifacts": self.artifacts.content_address,
                        "view": self.view.content_address,
                        "queue": self.queue.content_address,
                        "trace": self.trace.content_address,
                        "accessibility": self.accessibility.content_address,
                        "boundary": self.boundary.content_address,
                        "invariants": self.invariants.content_address,
                        "scenarios": self.scenarios.content_address,
                        "thresholds": self.thresholds.content_address,
                        "validation": self.validation.content_address,
                        "replay": self.replay.content_address,
                    }
                ),
            )

    def addresses(self) -> tuple[str, ...]:
        return (
            self.fixture.content_address,
            self.runtime.content_address,
            self.release.content_address,
            self.bundle.root_address,
            self.artifacts.content_address,
            self.view.content_address,
            self.queue.content_address,
            self.trace.content_address,
            self.accessibility.content_address,
            self.boundary.content_address,
            self.invariants.content_address,
            self.scenarios.content_address,
            self.thresholds.content_address,
            self.validation.content_address,
            self.replay.content_address,
            self.lineage.content_address,
            self.policy.content_address,
            self.schema.content_address,
            self.quality.content_address,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "fixture": self.fixture.to_dict(include_payload=False),
            "runtime": self.runtime.to_dict(),
            "release": self.release.to_dict(),
            "bundle": self.bundle.to_dict(),
            "artifacts": self.artifacts.to_dict(),
            "view": self.view.to_dict(),
            "queue": self.queue.to_dict(),
            "trace": self.trace.to_dict(),
            "accessibility": self.accessibility.to_dict(),
            "boundary": self.boundary.to_dict(),
            "invariants": self.invariants.to_dict(),
            "scenarios": self.scenarios.to_dict(),
            "thresholds": self.thresholds.to_dict(),
            "validation": self.validation.to_dict(),
            "replay": self.replay.to_dict(),
            "runbook": self.runbook.to_dict(),
            "content_address": self.content_address,
        }


def run_sequence_regulation_frontier_pipeline(
    fixture: SequenceRegulationFixture | None = None,
    *,
    run_id: str = "sequence-regulation-frontier",
) -> SequenceRegulationPipelineReport:
    fixture = fixture or default_sequence_regulation_fixture()
    runtime = run_sequence_regulation_runtime(
        SequenceRegulationRuntimeOptions(run_id), fixture=fixture
    )
    release = build_sequence_regulation_release(runtime)
    bundle = build_sequence_regulation_bundle(fixture, runtime.evaluation, release)
    artifacts = build_sequence_regulation_artifacts(runtime.quality, release, bundle)
    view = build_sequence_regulation_view(fixture, runtime.evaluation, runtime.policy)
    queue = build_sequence_regulation_review_queue(view)
    trace = build_sequence_regulation_trace(runtime, view)
    accessibility = audit_sequence_regulation_accessibility(fixture, view)
    boundary = audit_sequence_regulation_boundary(fixture)
    invariants = run_sequence_regulation_invariants(fixture, runtime.evaluation)
    scenarios = evaluate_sequence_regulation_scenarios(fixture, runtime.evaluation)
    thresholds = build_sequence_regulation_threshold_report()
    validation = build_sequence_regulation_validation_matrix(fixture, runtime.evaluation)
    replay = replay_sequence_regulation_evaluation(fixture)
    runbook = default_sequence_regulation_runbook()
    accepted = all(
        (
            runtime.accepted,
            release.accepted,
            bundle.accepted,
            artifacts.accepted,
            view.accepted,
            trace.accepted,
            accessibility.accepted,
            boundary.accepted,
            invariants.accepted,
            scenarios.accepted,
            thresholds.accepted,
            validation.accepted,
            replay.accepted,
            queue.accepted,
        )
    )
    return SequenceRegulationPipelineReport(
        fixture,
        runtime,
        release,
        bundle,
        artifacts,
        view,
        queue,
        trace,
        accessibility,
        boundary,
        invariants,
        scenarios,
        thresholds,
        validation,
        replay,
        runbook,
        accepted,
    )


__all__ = ["SequenceRegulationPipelineReport", "run_sequence_regulation_frontier_pipeline"]
