"""Command-oriented projections for the validation-beta frontier."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .validation_beta_frontier_adapters import default_validation_beta_frontier_adapters
from .validation_beta_frontier_contracts import default_validation_beta_frontier_contracts
from .validation_beta_frontier_exports import (
    export_validation_beta_frontier_json,
    export_validation_beta_frontier_review_csv,
    render_validation_beta_frontier_markdown,
)
from .validation_beta_frontier_fixture_eval import evaluate_validation_beta_frontier_fixture
from .validation_beta_frontier_governance import (
    assemble_validation_beta_frontier_bundle,
    audit_validation_beta_frontier_depth,
    build_validation_beta_frontier_artifact_inventory,
    build_validation_beta_frontier_claim_boundary,
    build_validation_beta_frontier_control_coverage,
    build_validation_beta_frontier_lineage,
    build_validation_beta_frontier_operational_matrix,
    build_validation_beta_frontier_release_manifest,
    build_validation_beta_frontier_review_queue,
    build_validation_beta_frontier_runbook,
    build_validation_beta_frontier_scenario_matrix,
    build_validation_beta_frontier_source_registry,
    evaluate_validation_beta_frontier_integrity,
    evaluate_validation_beta_frontier_quality,
    materialize_validation_beta_frontier_policy,
    measure_validation_beta_frontier,
    reconcile_validation_beta_frontier,
    replay_validation_beta_frontier,
    run_validation_beta_frontier_failure_injections,
    validation_beta_frontier_summary,
)
from .validation_beta_frontier_public_data import (
    audit_validation_beta_frontier_data,
    default_validation_beta_frontier_fixture,
    load_validation_beta_frontier_fixture,
)
from .validation_beta_frontier_runtime import run_validation_beta_frontier_runtime
from .validation_beta_frontier_schema import default_validation_beta_frontier_schema
from .validation_beta_frontier_handoff import build_validation_beta_frontier_handoff
from .validation_beta_frontier_thresholds import build_validation_beta_frontier_threshold_report
from .validation_beta_frontier_validation_matrix import build_validation_beta_frontier_validation_matrix
from .validation_beta_frontier_transcript import render_validation_beta_frontier_transcript

VALIDATION_BETA_FRONTIER_COMMANDS = (
    "validation-beta-frontier-fixture",
    "validation-beta-frontier-data",
    "validation-beta-frontier-evaluate",
    "validation-beta-frontier-contracts",
    "validation-beta-frontier-schema",
    "validation-beta-frontier-metrics",
    "validation-beta-frontier-lineage",
    "validation-beta-frontier-policy",
    "validation-beta-frontier-reconciliation",
    "validation-beta-frontier-quality",
    "validation-beta-frontier-replay",
    "validation-beta-frontier-review",
    "validation-beta-frontier-scenarios",
    "validation-beta-frontier-depth",
    "validation-beta-frontier-thresholds",
    "validation-beta-frontier-validation-matrix",
    "validation-beta-frontier-handoff",
    "validation-beta-frontier-artifacts",
    "validation-beta-frontier-controls",
    "validation-beta-frontier-operational",
    "validation-beta-frontier-integrity",
    "validation-beta-frontier-failures",
    "validation-beta-frontier-release",
    "validation-beta-frontier-bundle",
    "validation-beta-frontier-runbook",
    "validation-beta-frontier-summary",
    "validation-beta-frontier-report",
    "run-validation-beta-frontier-pipeline",
)


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierCliResult:
    payload: Any
    accepted: bool
    format: str = "json"


def _fixture(input_path: str | None):
    return load_validation_beta_frontier_fixture(input_path) if input_path else default_validation_beta_frontier_fixture()


def run_validation_beta_frontier_operation(
    command: str,
    *,
    input_path: str | None = None,
    output_format: str = "json",
) -> ValidationBetaFrontierCliResult:
    """Execute one CLI operation without writing to the filesystem."""

    if command not in VALIDATION_BETA_FRONTIER_COMMANDS:
        raise ValueError(f"unknown validation beta frontier command: {command}")
    fixture = _fixture(input_path)
    if command == "validation-beta-frontier-fixture":
        return ValidationBetaFrontierCliResult(fixture.to_dict(), True)
    if command == "validation-beta-frontier-data":
        audit = audit_validation_beta_frontier_data(fixture)
        return ValidationBetaFrontierCliResult(audit.to_dict(), audit.accepted)
    evaluation = evaluate_validation_beta_frontier_fixture(fixture)
    if command == "validation-beta-frontier-evaluate":
        return ValidationBetaFrontierCliResult(evaluation.to_dict(), evaluation.accepted)
    if command == "validation-beta-frontier-contracts":
        value = default_validation_beta_frontier_contracts()
        return ValidationBetaFrontierCliResult(value.to_dict(), True)
    if command == "validation-beta-frontier-schema":
        value = default_validation_beta_frontier_schema()
        return ValidationBetaFrontierCliResult(value.to_dict(), value.accepted)
    metrics = measure_validation_beta_frontier(evaluation)
    lineage = build_validation_beta_frontier_lineage(fixture, evaluation)
    policy = materialize_validation_beta_frontier_policy(evaluation)
    reconciliation = reconcile_validation_beta_frontier(fixture, evaluation)
    quality = evaluate_validation_beta_frontier_quality(fixture, evaluation, lineage=lineage, reconciliation=reconciliation)
    replay = replay_validation_beta_frontier(fixture)
    release = build_validation_beta_frontier_release_manifest(quality, replay, policy)
    if command == "validation-beta-frontier-metrics":
        return ValidationBetaFrontierCliResult(metrics.to_dict(), True)
    if command == "validation-beta-frontier-lineage":
        return ValidationBetaFrontierCliResult(lineage.to_dict(), lineage.closed)
    if command == "validation-beta-frontier-policy":
        return ValidationBetaFrontierCliResult(policy.to_dict(), True)
    if command == "validation-beta-frontier-reconciliation":
        return ValidationBetaFrontierCliResult(reconciliation.to_dict(), reconciliation.reconciled)
    if command == "validation-beta-frontier-quality":
        return ValidationBetaFrontierCliResult(quality.to_dict(), quality.accepted)
    if command == "validation-beta-frontier-replay":
        return ValidationBetaFrontierCliResult(replay.to_dict(), replay.deterministic)
    review = build_validation_beta_frontier_review_queue(evaluation, policy)
    if command == "validation-beta-frontier-review":
        return ValidationBetaFrontierCliResult(review.to_dict(), review.accepted)
    scenarios = build_validation_beta_frontier_scenario_matrix(evaluation, policy)
    if command == "validation-beta-frontier-scenarios":
        return ValidationBetaFrontierCliResult(scenarios.to_dict(), scenarios.accepted)
    depth = audit_validation_beta_frontier_depth(fixture, evaluation, metrics, lineage, quality)
    if command == "validation-beta-frontier-depth":
        return ValidationBetaFrontierCliResult(depth.to_dict(), depth.accepted)
    thresholds = build_validation_beta_frontier_threshold_report()
    if command == "validation-beta-frontier-thresholds":
        return ValidationBetaFrontierCliResult(thresholds.to_dict(), thresholds.accepted)
    validation_matrix = build_validation_beta_frontier_validation_matrix(fixture, evaluation)
    if command == "validation-beta-frontier-validation-matrix":
        return ValidationBetaFrontierCliResult(validation_matrix.to_dict(), validation_matrix.accepted)
    handoff = build_validation_beta_frontier_handoff(fixture, evaluation)
    if command == "validation-beta-frontier-handoff":
        return ValidationBetaFrontierCliResult(handoff.to_dict(), handoff.accepted)
    artifacts = build_validation_beta_frontier_artifact_inventory(fixture, evaluation)
    if command == "validation-beta-frontier-artifacts":
        return ValidationBetaFrontierCliResult(artifacts.to_dict(), artifacts.closed)
    controls = build_validation_beta_frontier_control_coverage(evaluation)
    if command == "validation-beta-frontier-controls":
        return ValidationBetaFrontierCliResult(controls.to_dict(), controls.accepted)
    operational = build_validation_beta_frontier_operational_matrix(policy)
    if command == "validation-beta-frontier-operational":
        return ValidationBetaFrontierCliResult(operational.to_dict(), operational.accepted)
    integrity = evaluate_validation_beta_frontier_integrity(fixture, evaluation)
    if command == "validation-beta-frontier-integrity":
        return ValidationBetaFrontierCliResult(integrity.to_dict(), integrity.accepted)
    failures = run_validation_beta_frontier_failure_injections(fixture)
    if command == "validation-beta-frontier-failures":
        return ValidationBetaFrontierCliResult(failures.to_dict(), failures.accepted)
    if command == "validation-beta-frontier-release":
        return ValidationBetaFrontierCliResult(release.to_dict() | {"ready": release.ready}, release.ready)
    bundle = assemble_validation_beta_frontier_bundle(fixture, evaluation, lineage, policy, quality, release)
    if command == "validation-beta-frontier-bundle":
        return ValidationBetaFrontierCliResult(bundle.to_dict() | {"accepted": bundle.publishable}, bundle.publishable)
    runbook = build_validation_beta_frontier_runbook()
    if command == "validation-beta-frontier-runbook":
        return ValidationBetaFrontierCliResult(runbook.to_dict(), runbook.executable)
    if command == "validation-beta-frontier-summary":
        return ValidationBetaFrontierCliResult(validation_beta_frontier_summary(fixture, evaluation, quality, release), quality.accepted)
    if command == "validation-beta-frontier-report":
        if output_format == "csv":
            return ValidationBetaFrontierCliResult(export_validation_beta_frontier_review_csv(evaluation), evaluation.accepted, "text")
        if output_format == "markdown":
            return ValidationBetaFrontierCliResult(render_validation_beta_frontier_markdown(evaluation), evaluation.accepted, "text")
        return ValidationBetaFrontierCliResult(export_validation_beta_frontier_json(evaluation), evaluation.accepted, "text")
    if command == "run-validation-beta-frontier-pipeline":
        runtime = run_validation_beta_frontier_runtime(fixture)
        return ValidationBetaFrontierCliResult(runtime.to_dict(), runtime.accepted)
    raise AssertionError(command)


__all__ = ["VALIDATION_BETA_FRONTIER_COMMANDS", "ValidationBetaFrontierCliResult", "run_validation_beta_frontier_operation"]
