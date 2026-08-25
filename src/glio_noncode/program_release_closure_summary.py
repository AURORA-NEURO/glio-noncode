"""Human-readable and machine-readable denominator summary."""

from __future__ import annotations

from .program_release_closure_bundle import program_release_snapshot_counts
from .program_release_closure_contracts import (
    ProgramReleaseClosurePlane,
    ProgramReleaseSnapshot,
    ProgramReleaseSummary,
    ProgramReleaseSummaryAudit,
    program_release_closure_check,
)
from .program_release_closure_reconciliation import _source_denominators
from .program_release_closure_support import csv_payload, markdown_payload
from .program_runtime_offline_contracts import ProgramRuntimeOfflineBundle
from .serialization import content_hash


def build_program_release_closure_summary(
    snapshot: ProgramReleaseSnapshot, source_bundle: ProgramRuntimeOfflineBundle
) -> ProgramReleaseSummary:
    source = _source_denominators(source_bundle)
    counts = program_release_snapshot_counts(snapshot)
    counters: tuple[tuple[str, int | float], ...] = tuple(
        sorted(
            {
                **{key: int(value) for key, value in counts.items() if key != "accepted"},
                "source_domain_count": source["source_domains"],
                "program_check_count": source["source_program_checks"],
                "quality_check_count": source["source_quality_checks"],
                "source_runtime_stage_count": source["source_runtime_stages"],
                "release_artifact_count": source["source_release_artifacts"],
                "domain_artifact_total": source["source_domain_artifact_total"],
                "evaluation_check_total": source["source_evaluation_check_total"],
                "stage_total": source["source_stage_total"],
            }.items()
        )
    )
    domains = tuple(
        {
            "domain_id": item.domain_id,
            "domain": item.domain,
            "stage_count": item.stage_count,
            "evaluation_check_count": item.evaluation_check_count,
            "source_artifact_count": item.source_artifact_count,
            "accepted": item.accepted,
            "content_address": item.content_address,
        }
        for item in snapshot.domains
    )
    body = {
        "bundle_id": snapshot.bundle_id,
        "counters": counters,
        "domains": domains,
        "accepted": snapshot.accepted,
    }
    return ProgramReleaseSummary(
        snapshot.bundle_id,
        counters,
        domains,
        snapshot.accepted,
        content_hash(body, prefix="program-release-summary"),
    )


def audit_program_release_closure_summary(
    summary: ProgramReleaseSummary, source_bundle: ProgramRuntimeOfflineBundle
) -> ProgramReleaseSummaryAudit:
    source = _source_denominators(source_bundle)
    values = summary.counter_map
    pairs = (
        ("domain_count", 16),
        ("artifact_count", 18),
        ("dependency_count", 120),
        ("gate_count", 96),
        ("source_domain_count", source["source_domains"]),
        ("program_check_count", source["source_program_checks"]),
        ("quality_check_count", source["source_quality_checks"]),
        ("source_runtime_stage_count", source["source_runtime_stages"]),
        ("release_artifact_count", source["source_release_artifacts"]),
        ("domain_artifact_total", source["source_domain_artifact_total"]),
        ("evaluation_check_total", source["source_evaluation_check_total"]),
        ("stage_total", source["source_stage_total"]),
    )
    checks = tuple(
        program_release_closure_check(
            f"summary:{key}",
            ProgramReleaseClosurePlane.RECONCILIATION,
            values.get(key) == expected,
            values.get(key),
            expected,
            f"summary counter {key} is conserved",
        )
        for key, expected in pairs
    ) + (
        program_release_closure_check(
            "summary:accepted",
            ProgramReleaseClosurePlane.RECONCILIATION,
            summary.accepted,
            summary.accepted,
            True,
            "summary follows aggregate acceptance",
        ),
    )
    accepted = all(item.passed for item in checks)
    body = {"bundle_id": summary.bundle_id, "checks": checks, "accepted": accepted}
    return ProgramReleaseSummaryAudit(
        summary.bundle_id,
        checks,
        accepted,
        content_hash(body, prefix="program-release-summary-audit"),
    )


def export_program_release_summary_csv(summary: ProgramReleaseSummary) -> bytes:
    return csv_payload(({"counter": key, "value": value} for key, value in summary.counters))


def export_program_release_summary_markdown(summary: ProgramReleaseSummary) -> bytes:
    return markdown_payload(
        "Program release closure summary",
        ({"counter": key, "value": value} for key, value in summary.counters),
    )


__all__ = [
    name
    for name in globals()
    if name.startswith("build_program_release")
    or name.startswith("audit_program_release")
    or name.startswith("export_program_release")
    or name.startswith("ProgramRelease")
]
