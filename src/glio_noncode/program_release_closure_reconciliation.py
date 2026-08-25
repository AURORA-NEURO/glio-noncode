"""Reconcile the aggregate closure against the source offline handoff."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .program_release_closure_bundle import program_release_snapshot_counts
from .program_release_closure_contracts import (
    ProgramReleaseClosureCheck,
    ProgramReleaseClosurePlane,
    ProgramReleaseReconciliation,
    ProgramReleaseSnapshot,
    program_release_closure_check,
)
from .program_release_closure_support import as_int, source_report, source_rows
from .program_runtime_offline_contracts import ProgramRuntimeOfflineBundle
from .serialization import content_hash


def _check(
    check_id: str, passed: bool, observed: Any, expected: Any, detail: str
) -> ProgramReleaseClosureCheck:
    return program_release_closure_check(
        check_id, ProgramReleaseClosurePlane.RECONCILIATION, passed, observed, expected, detail
    )


def _source_denominators(source: ProgramRuntimeOfflineBundle) -> dict[str, int]:
    report = source_report(source)
    quality = source_rows(source, "quality")
    operations = source_rows(source, "operations")
    stages = source_rows(source, "stages")
    checks = source_rows(source, "checks")
    release_artifact_ids = {
        "runtime",
        "report",
        "summary",
        "receipts",
        "checks",
        "domains",
        "markdown",
        "replay",
        "failure-controls",
        "specifications",
        "matrix",
    }
    return {
        "source_domains": len(operations) if isinstance(operations, list) else 0,
        "source_program_checks": len(checks) if isinstance(checks, list) else 0,
        "source_quality_checks": len(quality.get("checks", ()))
        if isinstance(quality, Mapping)
        else len(quality)
        if isinstance(quality, list)
        else 0,
        "source_runtime_stages": len(stages) if isinstance(stages, list) else 0,
        "source_release_artifacts": sum(
            item.artifact_id in release_artifact_ids for item in source.artifacts
        ),
        "source_domain_artifact_total": as_int(report.get("total_artifact_count")),
        "source_evaluation_check_total": as_int(report.get("total_evaluation_check_count")),
        "source_stage_total": as_int(report.get("total_stage_count")),
    }


def reconcile_program_release_closure(
    snapshot: ProgramReleaseSnapshot, source_bundle: ProgramRuntimeOfflineBundle
) -> ProgramReleaseReconciliation:
    """Issue explicit conservation receipts for source and aggregate denominators."""

    source = _source_denominators(source_bundle)
    counts = program_release_snapshot_counts(snapshot)
    expected = {
        "source_domains": 16,
        "source_program_checks": 172,
        "source_quality_checks": 18,
        "source_runtime_stages": 12,
        "source_release_artifacts": 11,
        "source_domain_artifact_total": 98,
        "source_evaluation_check_total": 7178,
        "source_stage_total": 380,
    }
    checks: list[ProgramReleaseClosureCheck] = [
        _check(
            "source-bundle-ready",
            source_bundle.ready,
            source_bundle.state.value,
            "ready",
            "source offline handoff is accepted",
        ),
        _check(
            "source-bundle-address",
            bool(source_bundle.content_address),
            source_bundle.content_address,
            "addressed",
            "source handoff is content-addressed",
        ),
        _check(
            "source-domain-denominator",
            source["source_domains"] == expected["source_domains"],
            source["source_domains"],
            expected["source_domains"],
            "source operations conserve sixteen domains",
        ),
        _check(
            "source-program-check-denominator",
            source["source_program_checks"] == expected["source_program_checks"],
            source["source_program_checks"],
            expected["source_program_checks"],
            "source program checks are conserved",
        ),
        _check(
            "source-quality-check-denominator",
            source["source_quality_checks"] == expected["source_quality_checks"],
            source["source_quality_checks"],
            expected["source_quality_checks"],
            "source quality checks are conserved",
        ),
        _check(
            "source-runtime-stage-denominator",
            source["source_runtime_stages"] == expected["source_runtime_stages"],
            source["source_runtime_stages"],
            expected["source_runtime_stages"],
            "source runtime stages are conserved",
        ),
        _check(
            "source-release-artifact-denominator",
            source["source_release_artifacts"] == expected["source_release_artifacts"],
            source["source_release_artifacts"],
            expected["source_release_artifacts"],
            "source release projection count is conserved",
        ),
        _check(
            "source-domain-artifact-total",
            source["source_domain_artifact_total"] == expected["source_domain_artifact_total"],
            source["source_domain_artifact_total"],
            expected["source_domain_artifact_total"],
            "source domain artifact total is conserved",
        ),
        _check(
            "source-evaluation-total",
            source["source_evaluation_check_total"] == expected["source_evaluation_check_total"],
            source["source_evaluation_check_total"],
            expected["source_evaluation_check_total"],
            "source evaluation total is conserved",
        ),
        _check(
            "source-stage-total",
            source["source_stage_total"] == expected["source_stage_total"],
            source["source_stage_total"],
            expected["source_stage_total"],
            "source stage total is conserved",
        ),
        _check(
            "aggregate-domain-denominator",
            counts["domain_count"] == 16,
            counts["domain_count"],
            16,
            "aggregate domains conserve source domains",
        ),
        _check(
            "aggregate-artifact-denominator",
            counts["artifact_count"] == 18,
            counts["artifact_count"],
            18,
            "aggregate artifacts conserve offline artifacts",
        ),
        _check(
            "aggregate-dependency-denominator",
            counts["dependency_count"] == 120,
            counts["dependency_count"],
            120,
            "aggregate dependency matrix is complete",
        ),
        _check(
            "aggregate-gate-denominator",
            counts["gate_count"] == 96,
            counts["gate_count"],
            96,
            "aggregate gates conserve six gates per domain",
        ),
        _check(
            "aggregate-domain-acceptance",
            counts["accepted_domain_count"] == 16,
            counts["accepted_domain_count"],
            16,
            "every aggregate domain is accepted",
        ),
        _check(
            "aggregate-gate-acceptance",
            counts["passed_gate_count"] == 96,
            counts["passed_gate_count"],
            96,
            "every aggregate gate passes",
        ),
        _check(
            "domain-sum-artifacts",
            sum(item.source_artifact_count for item in snapshot.domains)
            == source["source_domain_artifact_total"],
            sum(item.source_artifact_count for item in snapshot.domains),
            source["source_domain_artifact_total"],
            "domain artifact contributions sum to source total",
        ),
        _check(
            "domain-sum-evaluations",
            sum(item.evaluation_check_count for item in snapshot.domains)
            == source["source_evaluation_check_total"],
            sum(item.evaluation_check_count for item in snapshot.domains),
            source["source_evaluation_check_total"],
            "domain evaluation contributions sum to source total",
        ),
        _check(
            "domain-sum-stages",
            sum(item.stage_count for item in snapshot.domains) == source["source_stage_total"],
            sum(item.stage_count for item in snapshot.domains),
            source["source_stage_total"],
            "domain stage contributions sum to source total",
        ),
    ]
    accepted = all(item.passed for item in checks)
    body = {"bundle_id": snapshot.bundle_id, "checks": checks, "accepted": accepted}
    return ProgramReleaseReconciliation(
        snapshot.bundle_id,
        tuple(checks),
        accepted,
        content_hash(body, prefix="program-release-reconciliation"),
    )


def diff_program_release_closures(
    left: ProgramReleaseSnapshot, right: ProgramReleaseSnapshot
) -> dict[str, Any]:
    """Compare two projections by stable identities and addresses."""

    def compare(resource: str, key: str) -> dict[str, tuple[str, ...]]:
        left_values = {
            str(getattr(item, key)): str(item.content_address) for item in getattr(left, resource)
        }
        right_values = {
            str(getattr(item, key)): str(item.content_address) for item in getattr(right, resource)
        }
        return {
            "added": tuple(sorted(set(right_values) - set(left_values))),
            "removed": tuple(sorted(set(left_values) - set(right_values))),
            "changed": tuple(
                sorted(
                    key
                    for key in set(left_values) & set(right_values)
                    if left_values[key] != right_values[key]
                )
            ),
        }

    body = {
        "left_bundle_id": left.bundle_id,
        "right_bundle_id": right.bundle_id,
        "domains": compare("domains", "domain_id"),
        "artifacts": compare("artifacts", "artifact_ref"),
        "dependencies": compare("dependencies", "dependency_id"),
        "gates": compare("gates", "gate_id"),
    }
    body["accepted"] = all(
        not value["added"] and not value["removed"] and not value["changed"]
        for key, value in body.items()
        if key in {"domains", "artifacts", "dependencies", "gates"}
    )
    body["content_address"] = content_hash(body, prefix="program-release-diff")
    return body


__all__ = [
    name
    for name in globals()
    if name.startswith("reconcile_program_release")
    or name.startswith("diff_program_release")
    or name.startswith("ProgramRelease")
    or name.startswith("_source")
]
