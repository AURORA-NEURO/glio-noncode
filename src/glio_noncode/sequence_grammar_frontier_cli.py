"""CLI operation dispatch for the sequence grammar beta frontier."""

from __future__ import annotations

from typing import Any

from .sequence_grammar_frontier_accessibility import audit_sequence_grammar_accessibility
from .sequence_grammar_frontier_artifacts import build_sequence_grammar_artifacts
from .sequence_grammar_frontier_bundle import build_sequence_grammar_bundle
from .sequence_grammar_frontier_checks import run_sequence_grammar_invariants
from .sequence_grammar_frontier_compliance import audit_sequence_grammar_boundary
from .sequence_grammar_frontier_contracts import default_sequence_grammar_contracts
from .sequence_grammar_frontier_exports import (
    export_sequence_grammar_review_csv,
    render_sequence_grammar_release_markdown,
    render_sequence_grammar_review_markdown,
)
from .sequence_grammar_frontier_fixture_eval import evaluate_sequence_grammar_fixture
from .sequence_grammar_frontier_lineage import build_sequence_grammar_lineage
from .sequence_grammar_frontier_metrics import compute_sequence_grammar_metrics
from .sequence_grammar_frontier_pipeline import run_sequence_grammar_frontier_pipeline
from .sequence_grammar_frontier_policy import evaluate_sequence_grammar_policy
from .sequence_grammar_frontier_public_data import (
    SequenceGrammarFixture,
    audit_sequence_grammar_data,
    default_sequence_grammar_fixture,
    load_sequence_grammar_fixture,
)
from .sequence_grammar_frontier_quality_gate import run_sequence_grammar_quality_gate
from .sequence_grammar_frontier_release import build_sequence_grammar_release
from .sequence_grammar_frontier_replay import replay_sequence_grammar_evaluation
from .sequence_grammar_frontier_review_queue import build_sequence_grammar_review_queue
from .sequence_grammar_frontier_runbook import default_sequence_grammar_runbook
from .sequence_grammar_frontier_runtime import (
    SequenceGrammarRuntimeOptions,
    run_sequence_grammar_pipeline,
)
from .sequence_grammar_frontier_scenario_matrix import evaluate_sequence_grammar_scenarios
from .sequence_grammar_frontier_schema import validate_sequence_grammar_schema
from .sequence_grammar_frontier_thresholds import build_sequence_grammar_threshold_report
from .sequence_grammar_frontier_validation_matrix import build_sequence_grammar_validation_matrix
from .sequence_grammar_frontier_views import build_sequence_grammar_view

SEQUENCE_GRAMMAR_FRONTIER_COMMANDS = (
    "sequence-grammar-data-audit",
    "sequence-grammar-contracts",
    "sequence-grammar-schema",
    "sequence-grammar-evaluate",
    "sequence-grammar-replay",
    "sequence-grammar-quality-gate",
    "sequence-grammar-runtime",
    "sequence-grammar-metrics",
    "sequence-grammar-lineage",
    "sequence-grammar-policy",
    "sequence-grammar-release",
    "sequence-grammar-bundle",
    "sequence-grammar-artifacts",
    "sequence-grammar-view",
    "sequence-grammar-review-queue",
    "export-sequence-grammar-review-csv",
    "sequence-grammar-accessibility",
    "sequence-grammar-compliance",
    "sequence-grammar-invariants",
    "sequence-grammar-adapters",
    "sequence-grammar-scenarios",
    "sequence-grammar-thresholds",
    "sequence-grammar-validation",
    "sequence-grammar-runbook",
    "sequence-grammar-pipeline",
)


def _fixture(value: SequenceGrammarFixture | str | None) -> SequenceGrammarFixture:
    if isinstance(value, SequenceGrammarFixture):
        return value
    return load_sequence_grammar_fixture(value) if value else default_sequence_grammar_fixture()


def run_sequence_grammar_operation(
    command: str,
    fixture: SequenceGrammarFixture | str | None = None,
    *,
    run_id: str = "sequence-grammar-cli",
) -> Any:
    if command not in SEQUENCE_GRAMMAR_FRONTIER_COMMANDS:
        raise ValueError(f"unknown sequence-grammar command: {command}")
    loaded = _fixture(fixture)
    evaluation = evaluate_sequence_grammar_fixture(loaded)
    if command == "sequence-grammar-data-audit":
        return audit_sequence_grammar_data(loaded)
    if command == "sequence-grammar-contracts":
        return default_sequence_grammar_contracts()
    if command == "sequence-grammar-schema":
        return validate_sequence_grammar_schema(loaded, evaluation)
    if command == "sequence-grammar-evaluate":
        return evaluation
    if command == "sequence-grammar-replay":
        return replay_sequence_grammar_evaluation(evaluation, loaded)
    if command == "sequence-grammar-quality-gate":
        return run_sequence_grammar_quality_gate(loaded)
    if command == "sequence-grammar-runtime":
        return run_sequence_grammar_pipeline(
            SequenceGrammarRuntimeOptions(run_id=run_id), fixture=loaded
        )
    if command == "sequence-grammar-metrics":
        return compute_sequence_grammar_metrics(evaluation)
    if command == "sequence-grammar-lineage":
        return build_sequence_grammar_lineage(loaded, evaluation)
    if command == "sequence-grammar-policy":
        return evaluate_sequence_grammar_policy(loaded, evaluation)
    if command == "sequence-grammar-release":
        runtime = run_sequence_grammar_pipeline(
            SequenceGrammarRuntimeOptions(run_id=run_id), fixture=loaded
        )
        return build_sequence_grammar_release(runtime.quality, runtime)
    if command == "sequence-grammar-bundle":
        runtime = run_sequence_grammar_pipeline(
            SequenceGrammarRuntimeOptions(run_id=run_id), fixture=loaded
        )
        return build_sequence_grammar_bundle(
            loaded, evaluation, build_sequence_grammar_release(runtime.quality, runtime)
        )
    if command == "sequence-grammar-artifacts":
        runtime = run_sequence_grammar_pipeline(
            SequenceGrammarRuntimeOptions(run_id=run_id), fixture=loaded
        )
        release = build_sequence_grammar_release(runtime.quality, runtime)
        return build_sequence_grammar_artifacts(
            runtime.quality, release, build_sequence_grammar_bundle(loaded, evaluation, release)
        )
    if command == "sequence-grammar-view":
        return build_sequence_grammar_view(
            loaded, evaluation, evaluate_sequence_grammar_policy(loaded, evaluation)
        )
    if command == "sequence-grammar-review-queue":
        view = build_sequence_grammar_view(
            loaded, evaluation, evaluate_sequence_grammar_policy(loaded, evaluation)
        )
        return build_sequence_grammar_review_queue(view)
    if command == "export-sequence-grammar-review-csv":
        return export_sequence_grammar_review_csv(
            build_sequence_grammar_view(
                loaded, evaluation, evaluate_sequence_grammar_policy(loaded, evaluation)
            )
        )
    if command == "sequence-grammar-accessibility":
        view = build_sequence_grammar_view(
            loaded, evaluation, evaluate_sequence_grammar_policy(loaded, evaluation)
        )
        return audit_sequence_grammar_accessibility(loaded, view)
    if command == "sequence-grammar-compliance":
        runtime = run_sequence_grammar_pipeline(
            SequenceGrammarRuntimeOptions(run_id=run_id), fixture=loaded
        )
        return audit_sequence_grammar_boundary(loaded, runtime)
    if command == "sequence-grammar-invariants":
        return run_sequence_grammar_invariants(loaded, evaluation)
    if command == "sequence-grammar-adapters":
        from .sequence_grammar_frontier_adapters import build_sequence_grammar_adapters

        return build_sequence_grammar_adapters()
    if command == "sequence-grammar-scenarios":
        return evaluate_sequence_grammar_scenarios(loaded, evaluation)
    if command == "sequence-grammar-thresholds":
        return build_sequence_grammar_threshold_report()
    if command == "sequence-grammar-validation":
        return build_sequence_grammar_validation_matrix(loaded, evaluation)
    if command == "sequence-grammar-runbook":
        return default_sequence_grammar_runbook()
    if command == "sequence-grammar-pipeline":
        return run_sequence_grammar_frontier_pipeline(loaded, run_id=run_id)
    raise AssertionError(command)


def sequence_grammar_operation_text(
    command: str,
    fixture: SequenceGrammarFixture | str | None = None,
    *,
    run_id: str = "sequence-grammar-cli",
) -> str:
    result = run_sequence_grammar_operation(command, fixture, run_id=run_id)
    if command == "export-sequence-grammar-review-csv":
        return str(result)
    loaded = _fixture(fixture)
    evaluation = evaluate_sequence_grammar_fixture(loaded)
    if command == "sequence-grammar-release":
        return render_sequence_grammar_release_markdown(loaded, result)
    if command == "sequence-grammar-view":
        return render_sequence_grammar_review_markdown(
            build_sequence_grammar_view(
                loaded, evaluation, evaluate_sequence_grammar_policy(loaded, evaluation)
            )
        )
    return str(result)


__all__ = [
    "SEQUENCE_GRAMMAR_FRONTIER_COMMANDS",
    "run_sequence_grammar_operation",
    "sequence_grammar_operation_text",
]
