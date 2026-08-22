"""CLI operation dispatch for the sequence-effect frontier."""

from __future__ import annotations

from typing import Any

from .sequence_effect_frontier_accessibility import audit_sequence_effect_accessibility
from .sequence_effect_frontier_adapters import build_sequence_effect_adapters
from .sequence_effect_frontier_artifacts import build_sequence_effect_artifacts
from .sequence_effect_frontier_bundle import build_sequence_effect_bundle
from .sequence_effect_frontier_checks import run_sequence_effect_invariants
from .sequence_effect_frontier_compliance import audit_sequence_effect_boundary
from .sequence_effect_frontier_contracts import default_sequence_effect_contracts
from .sequence_effect_frontier_exports import (
    export_sequence_effect_review_csv,
    render_sequence_effect_release_markdown,
    render_sequence_effect_review_markdown,
)
from .sequence_effect_frontier_fixture_eval import evaluate_sequence_effect_fixture
from .sequence_effect_frontier_lineage import build_sequence_effect_lineage
from .sequence_effect_frontier_metrics import compute_sequence_effect_metrics
from .sequence_effect_frontier_pipeline import run_sequence_effect_frontier_pipeline
from .sequence_effect_frontier_policy import evaluate_sequence_effect_policy
from .sequence_effect_frontier_public_data import (
    SequenceEffectFixture,
    audit_sequence_effect_data,
    default_sequence_effect_fixture,
    load_sequence_effect_fixture,
)
from .sequence_effect_frontier_quality_gate import run_sequence_effect_quality_gate
from .sequence_effect_frontier_release import build_sequence_effect_release
from .sequence_effect_frontier_replay import replay_sequence_effect_evaluation
from .sequence_effect_frontier_review_queue import build_sequence_effect_review_queue
from .sequence_effect_frontier_runbook import default_sequence_effect_runbook
from .sequence_effect_frontier_runtime import (
    SequenceEffectRuntimeOptions,
    run_sequence_effect_pipeline,
)
from .sequence_effect_frontier_scenario_matrix import evaluate_sequence_effect_scenarios
from .sequence_effect_frontier_schema import (
    validate_sequence_effect_schema,
)
from .sequence_effect_frontier_thresholds import build_sequence_effect_threshold_report
from .sequence_effect_frontier_validation_matrix import build_sequence_effect_validation_matrix
from .sequence_effect_frontier_views import build_sequence_effect_view

SEQUENCE_EFFECT_FRONTIER_COMMANDS = (
    "sequence-effect-data-audit",
    "sequence-effect-contracts",
    "sequence-effect-schema",
    "sequence-effect-evaluate",
    "sequence-effect-replay",
    "sequence-effect-quality-gate",
    "sequence-effect-runtime",
    "sequence-effect-metrics",
    "sequence-effect-lineage",
    "sequence-effect-policy",
    "sequence-effect-release",
    "sequence-effect-bundle",
    "sequence-effect-artifacts",
    "sequence-effect-view",
    "sequence-effect-review-queue",
    "export-sequence-effect-review-csv",
    "sequence-effect-accessibility",
    "sequence-effect-compliance",
    "sequence-effect-invariants",
    "sequence-effect-adapters",
    "sequence-effect-scenarios",
    "sequence-effect-thresholds",
    "sequence-effect-validation",
    "sequence-effect-runbook",
    "sequence-effect-pipeline",
)


def _fixture(value: SequenceEffectFixture | str | None) -> SequenceEffectFixture:
    if isinstance(value, SequenceEffectFixture):
        return value
    return load_sequence_effect_fixture(value) if value else default_sequence_effect_fixture()


def run_sequence_effect_operation(
    command: str,
    fixture: SequenceEffectFixture | str | None = None,
    *,
    run_id: str = "sequence-effect-cli",
) -> Any:
    if command not in SEQUENCE_EFFECT_FRONTIER_COMMANDS:
        raise ValueError(f"unknown sequence-effect command: {command}")
    loaded = _fixture(fixture)
    evaluation = evaluate_sequence_effect_fixture(loaded)
    if command == "sequence-effect-data-audit":
        return audit_sequence_effect_data(loaded)
    if command == "sequence-effect-contracts":
        return default_sequence_effect_contracts()
    if command == "sequence-effect-schema":
        return validate_sequence_effect_schema(loaded, evaluation)
    if command == "sequence-effect-evaluate":
        return evaluation
    if command == "sequence-effect-replay":
        return replay_sequence_effect_evaluation(evaluation, loaded)
    if command == "sequence-effect-quality-gate":
        return run_sequence_effect_quality_gate(loaded)
    if command == "sequence-effect-runtime":
        return run_sequence_effect_pipeline(
            SequenceEffectRuntimeOptions(run_id=run_id), fixture=loaded
        )
    if command == "sequence-effect-metrics":
        return compute_sequence_effect_metrics(evaluation)
    if command == "sequence-effect-lineage":
        return build_sequence_effect_lineage(loaded, evaluation)
    if command == "sequence-effect-policy":
        return evaluate_sequence_effect_policy(loaded, evaluation)
    if command == "sequence-effect-release":
        runtime = run_sequence_effect_pipeline(
            SequenceEffectRuntimeOptions(run_id=run_id), fixture=loaded
        )
        return build_sequence_effect_release(runtime.quality, runtime)
    if command == "sequence-effect-bundle":
        runtime = run_sequence_effect_pipeline(
            SequenceEffectRuntimeOptions(run_id=run_id), fixture=loaded
        )
        return build_sequence_effect_bundle(
            loaded, evaluation, build_sequence_effect_release(runtime.quality, runtime)
        )
    if command == "sequence-effect-artifacts":
        runtime = run_sequence_effect_pipeline(
            SequenceEffectRuntimeOptions(run_id=run_id), fixture=loaded
        )
        release = build_sequence_effect_release(runtime.quality, runtime)
        bundle = build_sequence_effect_bundle(loaded, evaluation, release)
        return build_sequence_effect_artifacts(runtime.quality, release, bundle)
    if command == "sequence-effect-view":
        return build_sequence_effect_view(loaded, evaluation)
    if command == "sequence-effect-review-queue":
        return build_sequence_effect_review_queue(build_sequence_effect_view(loaded, evaluation))
    if command == "export-sequence-effect-review-csv":
        return export_sequence_effect_review_csv(build_sequence_effect_view(loaded, evaluation))
    if command == "sequence-effect-accessibility":
        return audit_sequence_effect_accessibility(
            loaded, build_sequence_effect_view(loaded, evaluation)
        )
    if command == "sequence-effect-compliance":
        runtime = run_sequence_effect_pipeline(
            SequenceEffectRuntimeOptions(run_id=run_id), fixture=loaded
        )
        return audit_sequence_effect_boundary(loaded, runtime)
    if command == "sequence-effect-invariants":
        return run_sequence_effect_invariants(loaded, evaluation)
    if command == "sequence-effect-adapters":
        return build_sequence_effect_adapters()
    if command == "sequence-effect-scenarios":
        return evaluate_sequence_effect_scenarios(loaded, evaluation)
    if command == "sequence-effect-thresholds":
        return build_sequence_effect_threshold_report()
    if command == "sequence-effect-validation":
        return build_sequence_effect_validation_matrix(loaded, evaluation)
    if command == "sequence-effect-runbook":
        return default_sequence_effect_runbook()
    if command == "sequence-effect-pipeline":
        return run_sequence_effect_frontier_pipeline(loaded, run_id=run_id)
    raise AssertionError(command)


def sequence_effect_operation_text(
    command: str,
    fixture: SequenceEffectFixture | str | None = None,
    *,
    run_id: str = "sequence-effect-cli",
) -> str:
    result = run_sequence_effect_operation(command, fixture, run_id=run_id)
    if command == "export-sequence-effect-review-csv":
        return str(result)
    if command == "sequence-effect-review-queue":
        return export_sequence_effect_review_csv(
            build_sequence_effect_view(
                _fixture(fixture), evaluate_sequence_effect_fixture(_fixture(fixture))
            )
        )
    return (
        render_sequence_effect_release_markdown(_fixture(fixture), result)
        if command == "sequence-effect-release"
        else render_sequence_effect_review_markdown(
            build_sequence_effect_view(
                _fixture(fixture), evaluate_sequence_effect_fixture(_fixture(fixture))
            )
        )
        if command == "sequence-effect-view"
        else str(result)
    )


__all__ = [
    "SEQUENCE_EFFECT_FRONTIER_COMMANDS",
    "run_sequence_effect_operation",
    "sequence_effect_operation_text",
]
