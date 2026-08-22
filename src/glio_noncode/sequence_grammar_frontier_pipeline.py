"""End-to-end report for the Domain 06 C05-C08 frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sequence_grammar_frontier_accessibility import (
    SequenceGrammarAccessibilityReport,
    audit_sequence_grammar_accessibility,
)
from .sequence_grammar_frontier_artifacts import (
    SequenceGrammarArtifactInventory,
    build_sequence_grammar_artifacts,
)
from .sequence_grammar_frontier_bundle import SequenceGrammarBundle, build_sequence_grammar_bundle
from .sequence_grammar_frontier_checks import (
    SequenceGrammarInvariantReport,
    run_sequence_grammar_invariants,
)
from .sequence_grammar_frontier_compliance import (
    SequenceGrammarBoundaryReport,
    audit_sequence_grammar_boundary,
)
from .sequence_grammar_frontier_fixture_eval import SequenceGrammarEvaluation
from .sequence_grammar_frontier_lineage import SequenceGrammarLineage
from .sequence_grammar_frontier_observability import (
    SequenceGrammarTrace,
    build_sequence_grammar_trace,
)
from .sequence_grammar_frontier_policy import SequenceGrammarPolicyReport
from .sequence_grammar_frontier_public_data import (
    SequenceGrammarFixture,
    default_sequence_grammar_fixture,
)
from .sequence_grammar_frontier_quality_gate import SequenceGrammarQualityReport
from .sequence_grammar_frontier_release import (
    SequenceGrammarReleaseManifest,
    build_sequence_grammar_release,
)
from .sequence_grammar_frontier_replay import (
    SequenceGrammarReplayReport,
    replay_sequence_grammar_evaluation,
)
from .sequence_grammar_frontier_review_queue import (
    SequenceGrammarReviewQueue,
    build_sequence_grammar_review_queue,
)
from .sequence_grammar_frontier_runbook import (
    SequenceGrammarRunbook,
    default_sequence_grammar_runbook,
)
from .sequence_grammar_frontier_runtime import (
    SequenceGrammarRuntimeOptions,
    SequenceGrammarRuntimeReport,
    run_sequence_grammar_pipeline,
)
from .sequence_grammar_frontier_scenario_matrix import (
    SequenceGrammarScenarioReport,
    evaluate_sequence_grammar_scenarios,
)
from .sequence_grammar_frontier_schema import SequenceGrammarSchemaReport
from .sequence_grammar_frontier_thresholds import (
    SequenceGrammarThresholdReport,
    build_sequence_grammar_threshold_report,
)
from .sequence_grammar_frontier_validation_matrix import (
    SequenceGrammarValidationReport,
    build_sequence_grammar_validation_matrix,
)
from .sequence_grammar_frontier_views import SequenceGrammarView, build_sequence_grammar_view
from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class SequenceGrammarPipelineReport:
    fixture: SequenceGrammarFixture
    runtime: SequenceGrammarRuntimeReport
    release: SequenceGrammarReleaseManifest
    bundle: SequenceGrammarBundle
    artifacts: SequenceGrammarArtifactInventory
    view: SequenceGrammarView
    queue: SequenceGrammarReviewQueue
    trace: SequenceGrammarTrace
    accessibility: SequenceGrammarAccessibilityReport
    boundary: SequenceGrammarBoundaryReport
    invariants: SequenceGrammarInvariantReport
    scenarios: SequenceGrammarScenarioReport
    thresholds: SequenceGrammarThresholdReport
    validation: SequenceGrammarValidationReport
    replay: SequenceGrammarReplayReport
    runbook: SequenceGrammarRunbook
    accepted: bool
    content_address: str = ""

    @property
    def evaluation(self) -> SequenceGrammarEvaluation:
        return self.runtime.evaluation

    @property
    def lineage(self) -> SequenceGrammarLineage:
        return self.runtime.lineage

    @property
    def policy(self) -> SequenceGrammarPolicyReport:
        return self.runtime.policy

    @property
    def schema(self) -> SequenceGrammarSchemaReport:
        return self.runtime.schema

    @property
    def quality(self) -> SequenceGrammarQualityReport:
        return self.runtime.quality

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
            "fixture": self.fixture.to_dict(),
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


def run_sequence_grammar_frontier_pipeline(
    fixture: SequenceGrammarFixture | None = None, *, run_id: str = "sequence-grammar-frontier"
) -> SequenceGrammarPipelineReport:
    fixture = fixture or default_sequence_grammar_fixture()
    runtime = run_sequence_grammar_pipeline(
        SequenceGrammarRuntimeOptions(run_id=run_id), fixture=fixture
    )
    release = build_sequence_grammar_release(runtime.quality, runtime)
    bundle = build_sequence_grammar_bundle(fixture, runtime.evaluation, release)
    artifacts = build_sequence_grammar_artifacts(runtime.quality, release, bundle)
    view = build_sequence_grammar_view(fixture, runtime.evaluation, runtime.policy)
    queue = build_sequence_grammar_review_queue(view)
    trace = build_sequence_grammar_trace(runtime, view)
    accessibility = audit_sequence_grammar_accessibility(fixture, view)
    boundary = audit_sequence_grammar_boundary(fixture, runtime)
    invariants = run_sequence_grammar_invariants(fixture, runtime.evaluation)
    scenarios = evaluate_sequence_grammar_scenarios(fixture, runtime.evaluation)
    thresholds = build_sequence_grammar_threshold_report()
    validation = build_sequence_grammar_validation_matrix(fixture, runtime.evaluation)
    replay = replay_sequence_grammar_evaluation(runtime.evaluation, fixture)
    runbook = default_sequence_grammar_runbook()
    accepted = all(
        (
            runtime.accepted,
            release.accepted,
            bundle.accepted,
            artifacts.accepted,
            view.accepted,
            queue.accepted,
            trace.accepted,
            accessibility.accepted,
            boundary.accepted,
            invariants.accepted,
            scenarios.accepted,
            thresholds.accepted,
            validation.accepted,
            replay.accepted,
        )
    )
    return SequenceGrammarPipelineReport(
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


__all__ = ["SequenceGrammarPipelineReport", "run_sequence_grammar_frontier_pipeline"]
