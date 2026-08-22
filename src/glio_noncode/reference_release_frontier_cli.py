"""Command family router for the Domain 04 C13-C16 release frontier."""

from __future__ import annotations

import csv
import io
from typing import Any

from .reference_release_frontier_accessibility import evaluate_reference_release_accessibility
from .reference_release_frontier_adapters import default_reference_release_adapters
from .reference_release_frontier_artifacts import build_reference_release_artifact_inventory
from .reference_release_frontier_bundle import (
    assemble_reference_release_bundle,
)
from .reference_release_frontier_checks import run_reference_release_invariants
from .reference_release_frontier_compliance import evaluate_reference_release_boundary
from .reference_release_frontier_contracts import default_reference_release_contracts
from .reference_release_frontier_fixture_eval import evaluate_reference_release_fixture
from .reference_release_frontier_lineage import build_reference_release_lineage
from .reference_release_frontier_metrics import build_reference_release_metrics
from .reference_release_frontier_observability import observe_reference_release
from .reference_release_frontier_pipeline import run_reference_release_pipeline
from .reference_release_frontier_policy import evaluate_reference_release_policy
from .reference_release_frontier_public_data import (
    audit_reference_release_data,
    default_reference_release_fixture,
)
from .reference_release_frontier_release import build_reference_release_manifest
from .reference_release_frontier_replay import replay_reference_release_evaluation
from .reference_release_frontier_review_queue import build_reference_release_review_queue
from .reference_release_frontier_runbook import default_reference_release_runbook
from .reference_release_frontier_runtime import run_reference_release_runtime
from .reference_release_frontier_scenario_matrix import build_reference_release_scenario_matrix
from .reference_release_frontier_schema import default_reference_release_schema
from .reference_release_frontier_thresholds import build_reference_release_threshold_report
from .reference_release_frontier_validation_matrix import build_reference_release_validation_matrix
from .reference_release_frontier_views import build_reference_release_review_view

REFERENCE_RELEASE_COMMANDS = (
    "reference-release-data-audit",
    "reference-release-contracts",
    "reference-release-schema",
    "reference-release-evaluate",
    "reference-release-replay",
    "reference-release-metrics",
    "reference-release-lineage",
    "reference-release-policy",
    "reference-release-quality-gate",
    "reference-release-runtime",
    "reference-release-observability",
    "reference-release-release",
    "reference-release-bundle",
    "reference-release-artifacts",
    "reference-release-review-view",
    "reference-release-review-queue",
    "reference-release-accessibility",
    "reference-release-compliance",
    "reference-release-invariants",
    "reference-release-adapters",
    "reference-release-scenarios",
    "reference-release-thresholds",
    "reference-release-validation",
    "reference-release-runbook",
    "reference-release-pipeline",
    "export-reference-release-review-csv",
)


def _runtime(fixture: Any, suffix: str):
    return run_reference_release_runtime(fixture, run_id=f"reference-release-cli-{suffix}")


def _release(runtime: Any, suffix: str):
    return build_reference_release_manifest(
        runtime, release_id=f"reference-release-cli-{suffix}-release"
    )


def _bundle(fixture: Any, runtime: Any, release: Any, suffix: str):
    return assemble_reference_release_bundle(
        fixture, runtime, release, bundle_id=f"reference-release-cli-{suffix}-bundle"
    )


def _view(fixture: Any, runtime: Any, release: Any):
    return build_reference_release_review_view(fixture, runtime.evaluation, runtime.policy, release)


def _review_csv(view: Any) -> str:
    buffer = io.StringIO()
    fields = tuple(view.columns)
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in view.rows:
        values = row.to_dict()
        values["issue_codes"] = "|".join(values["issue_codes"])
        values["source_ids"] = "|".join(values["source_ids"])
        writer.writerow({field: values[field] for field in fields})
    return buffer.getvalue()


def run_reference_release_operation(command: str, fixture: Any = None) -> Any:
    """Run one named command against the supplied or built-in fixture."""

    fixture = fixture or default_reference_release_fixture()
    if command == "reference-release-data-audit":
        return audit_reference_release_data(fixture)
    if command == "reference-release-contracts":
        return default_reference_release_contracts()
    if command == "reference-release-schema":
        return default_reference_release_schema()
    if command == "reference-release-evaluate":
        return evaluate_reference_release_fixture(fixture)
    if command == "reference-release-replay":
        evaluation = evaluate_reference_release_fixture(fixture)
        return replay_reference_release_evaluation(
            evaluation, fixture=fixture, replay_id="reference-release-cli-replay"
        )
    if command == "reference-release-metrics":
        return build_reference_release_metrics(evaluate_reference_release_fixture(fixture))
    if command == "reference-release-lineage":
        evaluation = evaluate_reference_release_fixture(fixture)
        return build_reference_release_lineage(fixture, evaluation)
    if command == "reference-release-policy":
        evaluation = evaluate_reference_release_fixture(fixture)
        return evaluate_reference_release_policy(fixture, evaluation)
    if command == "reference-release-quality-gate":
        return _runtime(fixture, "quality").quality
    if command == "reference-release-runtime":
        return _runtime(fixture, "runtime")
    if command == "reference-release-observability":
        return observe_reference_release(_runtime(fixture, "observability"))
    if command == "reference-release-release":
        return _release(_runtime(fixture, "release"), "release")
    if command == "reference-release-bundle":
        runtime = _runtime(fixture, "bundle")
        return _bundle(fixture, runtime, _release(runtime, "bundle"), "bundle")
    if command == "reference-release-artifacts":
        runtime = _runtime(fixture, "artifacts")
        release = _release(runtime, "artifacts")
        return build_reference_release_artifact_inventory(
            runtime, release, _bundle(fixture, runtime, release, "artifacts")
        )
    if command == "reference-release-review-view":
        runtime = _runtime(fixture, "view")
        release = _release(runtime, "view")
        return _view(fixture, runtime, release)
    if command == "reference-release-review-queue":
        runtime = _runtime(fixture, "queue")
        release = _release(runtime, "queue")
        return build_reference_release_review_queue(_view(fixture, runtime, release), release)
    if command == "reference-release-accessibility":
        runtime = _runtime(fixture, "accessibility")
        release = _release(runtime, "accessibility")
        return evaluate_reference_release_accessibility(
            fixture, runtime.evaluation, _view(fixture, runtime, release)
        )
    if command == "reference-release-compliance":
        runtime = _runtime(fixture, "compliance")
        release = _release(runtime, "compliance")
        bundle = _bundle(fixture, runtime, release, "compliance")
        return evaluate_reference_release_boundary(
            fixture, runtime.evaluation, runtime, bundle, _view(fixture, runtime, release)
        )
    if command == "reference-release-invariants":
        runtime = _runtime(fixture, "invariants")
        release = _release(runtime, "invariants")
        bundle = _bundle(fixture, runtime, release, "invariants")
        return run_reference_release_invariants(
            fixture, runtime.evaluation, release, bundle, _view(fixture, runtime, release)
        )
    if command == "reference-release-adapters":
        return default_reference_release_adapters()
    if command == "reference-release-scenarios":
        return build_reference_release_scenario_matrix()
    if command == "reference-release-thresholds":
        runtime = _runtime(fixture, "thresholds")
        return build_reference_release_threshold_report(
            fixture, runtime.evaluation, runtime.metrics, runtime.lineage
        )
    if command == "reference-release-validation":
        runtime = _runtime(fixture, "validation")
        return build_reference_release_validation_matrix(fixture, runtime.evaluation)
    if command == "reference-release-runbook":
        return default_reference_release_runbook()
    if command == "reference-release-pipeline":
        return run_reference_release_pipeline(fixture)
    if command == "export-reference-release-review-csv":
        runtime = _runtime(fixture, "csv")
        release = _release(runtime, "csv")
        return _review_csv(_view(fixture, runtime, release))
    raise ValueError(f"unknown reference release command: {command}")


__all__ = ["REFERENCE_RELEASE_COMMANDS", "run_reference_release_operation"]
