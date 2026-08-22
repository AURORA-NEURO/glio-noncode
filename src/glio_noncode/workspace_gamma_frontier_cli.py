"""Command family router for the C09-C12 collaboration frontier."""

from __future__ import annotations

from typing import Any

from .workspace_gamma_frontier_accessibility import evaluate_gamma_frontier_accessibility
from .workspace_gamma_frontier_adapters import default_gamma_frontier_adapters
from .workspace_gamma_frontier_artifacts import build_gamma_frontier_artifact_inventory
from .workspace_gamma_frontier_bundle import assemble_gamma_frontier_bundle
from .workspace_gamma_frontier_checks import run_gamma_frontier_invariants
from .workspace_gamma_frontier_compliance import evaluate_gamma_frontier_boundary
from .workspace_gamma_frontier_contracts import default_gamma_frontier_contracts
from .workspace_gamma_frontier_exports import export_gamma_frontier_review_csv
from .workspace_gamma_frontier_fixture_eval import evaluate_gamma_frontier_fixture
from .workspace_gamma_frontier_lineage import build_gamma_frontier_lineage
from .workspace_gamma_frontier_metrics import measure_gamma_frontier
from .workspace_gamma_frontier_observability import observe_gamma_frontier
from .workspace_gamma_frontier_pipeline import run_gamma_frontier_pipeline
from .workspace_gamma_frontier_policy import default_gamma_frontier_policy
from .workspace_gamma_frontier_public_data import (
    audit_gamma_frontier_data,
    default_gamma_frontier_fixture,
)
from .workspace_gamma_frontier_release import build_gamma_frontier_release_manifest
from .workspace_gamma_frontier_replay import replay_gamma_frontier
from .workspace_gamma_frontier_review_queue import build_gamma_frontier_review_queue
from .workspace_gamma_frontier_runbook import default_gamma_frontier_runbook
from .workspace_gamma_frontier_runtime import run_gamma_frontier_runtime
from .workspace_gamma_frontier_scenario_matrix import build_gamma_frontier_scenario_matrix
from .workspace_gamma_frontier_schema import default_gamma_frontier_schema
from .workspace_gamma_frontier_thresholds import build_gamma_frontier_threshold_report
from .workspace_gamma_frontier_validation_matrix import build_gamma_frontier_validation_matrix
from .workspace_gamma_frontier_views import build_gamma_frontier_review_view

GAMMA_FRONTIER_COMMANDS = (
    "gamma-frontier-data-audit",
    "gamma-frontier-contracts",
    "gamma-frontier-schema",
    "gamma-frontier-evaluate",
    "gamma-frontier-replay",
    "gamma-frontier-metrics",
    "gamma-frontier-lineage",
    "gamma-frontier-policy",
    "gamma-frontier-quality-gate",
    "gamma-frontier-runtime",
    "gamma-frontier-observability",
    "gamma-frontier-artifacts",
    "gamma-frontier-bundle",
    "gamma-frontier-release",
    "gamma-frontier-review-queue",
    "gamma-frontier-accessibility",
    "gamma-frontier-compliance",
    "gamma-frontier-invariants",
    "gamma-frontier-adapters",
    "gamma-frontier-scenarios",
    "gamma-frontier-thresholds",
    "gamma-frontier-validation",
    "gamma-frontier-runbook",
    "gamma-frontier-pipeline",
    "export-gamma-frontier-review-csv",
)


def run_gamma_frontier_operation(command: str, fixture: Any = None) -> Any:
    """Run one named command against a supplied or built-in fixture."""

    fixture = fixture or default_gamma_frontier_fixture()
    evaluation = None
    runtime = None
    if command == "gamma-frontier-data-audit":
        return audit_gamma_frontier_data(fixture)
    if command == "gamma-frontier-contracts":
        return default_gamma_frontier_contracts()
    if command == "gamma-frontier-schema":
        return default_gamma_frontier_schema()
    if command == "gamma-frontier-evaluate":
        return evaluate_gamma_frontier_fixture(fixture)
    if command == "gamma-frontier-replay":
        return replay_gamma_frontier(fixture, replay_id="gamma-frontier-cli-replay")
    if command == "gamma-frontier-metrics":
        evaluation = evaluate_gamma_frontier_fixture(fixture)
        return measure_gamma_frontier(evaluation)
    if command == "gamma-frontier-lineage":
        evaluation = evaluate_gamma_frontier_fixture(fixture)
        return build_gamma_frontier_lineage(fixture, evaluation)
    if command == "gamma-frontier-policy":
        evaluation = evaluate_gamma_frontier_fixture(fixture)
        return {
            "policy": default_gamma_frontier_policy().to_dict(),
            "decisions": [
                item.to_dict() for item in default_gamma_frontier_policy().decide(evaluation)
            ],
        }
    if command == "gamma-frontier-quality-gate":
        runtime = run_gamma_frontier_runtime(fixture, run_id="gamma-frontier-cli-quality")
        return runtime.quality
    if command == "gamma-frontier-runtime":
        return run_gamma_frontier_runtime(fixture, run_id="gamma-frontier-cli")
    if command == "gamma-frontier-observability":
        runtime = run_gamma_frontier_runtime(fixture, run_id="gamma-frontier-cli-observability")
        return observe_gamma_frontier(runtime)
    if command == "gamma-frontier-artifacts":
        runtime = run_gamma_frontier_runtime(fixture, run_id="gamma-frontier-cli-artifacts")
        replay = replay_gamma_frontier(fixture, replay_id="gamma-frontier-cli-artifact-replay")
        release = build_gamma_frontier_release_manifest(
            runtime, replay, release_id="gamma-frontier-cli-artifact-release"
        )
        bundle = assemble_gamma_frontier_bundle(fixture, runtime, release)
        return build_gamma_frontier_artifact_inventory(runtime, bundle, release)
    if command == "gamma-frontier-bundle":
        runtime = run_gamma_frontier_runtime(fixture, run_id="gamma-frontier-cli-bundle")
        replay = replay_gamma_frontier(fixture, replay_id="gamma-frontier-cli-bundle-replay")
        release = build_gamma_frontier_release_manifest(
            runtime, replay, release_id="gamma-frontier-cli-bundle-release"
        )
        return assemble_gamma_frontier_bundle(fixture, runtime, release)
    if command == "gamma-frontier-release":
        runtime = run_gamma_frontier_runtime(fixture, run_id="gamma-frontier-cli-release")
        return build_gamma_frontier_release_manifest(
            runtime,
            replay_gamma_frontier(fixture, replay_id="gamma-frontier-cli-release-replay"),
            release_id="gamma-frontier-cli-release",
        )
    if command == "gamma-frontier-review-queue":
        runtime = run_gamma_frontier_runtime(fixture, run_id="gamma-frontier-cli-review")
        replay = replay_gamma_frontier(fixture, replay_id="gamma-frontier-cli-review-replay")
        release = build_gamma_frontier_release_manifest(
            runtime, replay, release_id="gamma-frontier-cli-review-release"
        )
        view = build_gamma_frontier_review_view(
            fixture, runtime.evaluation, runtime.policy_decisions, release
        )
        return build_gamma_frontier_review_queue(view, release)
    if command == "gamma-frontier-accessibility":
        evaluation = evaluate_gamma_frontier_fixture(fixture)
        return evaluate_gamma_frontier_accessibility(fixture, evaluation)
    if command == "gamma-frontier-compliance":
        evaluation = evaluate_gamma_frontier_fixture(fixture)
        return evaluate_gamma_frontier_boundary(fixture, evaluation)
    if command == "gamma-frontier-invariants":
        evaluation = evaluate_gamma_frontier_fixture(fixture)
        return run_gamma_frontier_invariants(fixture, evaluation)
    if command == "gamma-frontier-adapters":
        return default_gamma_frontier_adapters()
    if command == "gamma-frontier-scenarios":
        return build_gamma_frontier_scenario_matrix()
    if command == "gamma-frontier-thresholds":
        return build_gamma_frontier_threshold_report()
    if command == "gamma-frontier-validation":
        return build_gamma_frontier_validation_matrix()
    if command == "gamma-frontier-runbook":
        return default_gamma_frontier_runbook()
    if command == "gamma-frontier-pipeline":
        return run_gamma_frontier_pipeline(fixture)
    if command == "export-gamma-frontier-review-csv":
        runtime = run_gamma_frontier_runtime(fixture, run_id="gamma-frontier-cli-csv")
        replay = replay_gamma_frontier(fixture, replay_id="gamma-frontier-cli-csv-replay")
        release = build_gamma_frontier_release_manifest(
            runtime, replay, release_id="gamma-frontier-cli-csv-release"
        )
        view = build_gamma_frontier_review_view(
            fixture, runtime.evaluation, runtime.policy_decisions, release
        )
        return export_gamma_frontier_review_csv(view)
    raise ValueError(f"unknown gamma frontier command: {command}")


__all__ = ["GAMMA_FRONTIER_COMMANDS", "run_gamma_frontier_operation"]
