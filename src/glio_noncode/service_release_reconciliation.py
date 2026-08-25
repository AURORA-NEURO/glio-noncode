"""Independent denominator and source-address reconciliation."""

from __future__ import annotations

from .service_release_bundle import service_release_snapshot_counts
from .service_release_contracts import (
    SERVICE_RELEASE_ARTIFACT_COUNT,
    SERVICE_RELEASE_DEPENDENCY_COUNT,
    SERVICE_RELEASE_GATE_COUNT,
    SERVICE_RELEASE_SURFACE_COUNT,
    ServiceReleasePlane,
    ServiceReleaseReconciliation,
    ServiceReleaseSnapshot,
    ServiceReleaseSummary,
    ServiceReleaseSummaryAudit,
    check,
)
from .service_release_support import csv_payload, markdown_payload
from .service_surface import ServiceSurfaceSnapshot
from .serialization import content_hash


def reconcile_service_release(
    snapshot: ServiceReleaseSnapshot,
    source_snapshot: ServiceSurfaceSnapshot,
) -> ServiceReleaseReconciliation:
    """Compare the registry with the cached service snapshot independently."""

    checks = [
        check(
            "reconciliation:source-address",
            ServiceReleasePlane.RECONCILIATION,
            snapshot.source_surface_address == source_snapshot.content_address,
            snapshot.source_surface_address,
            source_snapshot.content_address,
            "release source is the addressed service snapshot",
        ),
        check(
            "reconciliation:service-accepted",
            ServiceReleasePlane.RECONCILIATION,
            source_snapshot.accepted == snapshot.accepted,
            source_snapshot.accepted,
            snapshot.accepted,
            "registry acceptance follows the source surface",
        ),
        check(
            "reconciliation:surface-count",
            ServiceReleasePlane.RECONCILIATION,
            len(snapshot.surfaces) == SERVICE_RELEASE_SURFACE_COUNT,
            len(snapshot.surfaces),
            SERVICE_RELEASE_SURFACE_COUNT,
            "all service surface domains are present",
        ),
        check(
            "reconciliation:artifact-count",
            ServiceReleasePlane.RECONCILIATION,
            len(snapshot.artifacts) == SERVICE_RELEASE_ARTIFACT_COUNT,
            len(snapshot.artifacts),
            SERVICE_RELEASE_ARTIFACT_COUNT,
            "all exact-byte release artifacts are present",
        ),
        check(
            "reconciliation:dependency-count",
            ServiceReleasePlane.RECONCILIATION,
            len(snapshot.dependencies) == SERVICE_RELEASE_DEPENDENCY_COUNT,
            len(snapshot.dependencies),
            SERVICE_RELEASE_DEPENDENCY_COUNT,
            "complete forward surface dependency matrix is present",
        ),
        check(
            "reconciliation:gate-count",
            ServiceReleasePlane.RECONCILIATION,
            len(snapshot.gates) == SERVICE_RELEASE_GATE_COUNT,
            len(snapshot.gates),
            SERVICE_RELEASE_GATE_COUNT,
            "every surface has all promotion gates",
        ),
        check(
            "reconciliation:program-release-source",
            ServiceReleasePlane.SOURCE,
            snapshot.surface_map["program-release"].source_address == source_snapshot.program_release.content_address,
            snapshot.surface_map["program-release"].source_address,
            source_snapshot.program_release.content_address,
            "top-level D01-D16 snapshot is registered without mutation",
        ),
        check(
            "reconciliation:surface-addresses",
            ServiceReleasePlane.SOURCE,
            all(item.source_address for item in snapshot.surfaces),
            sum(bool(item.source_address) for item in snapshot.surfaces),
            len(snapshot.surfaces),
            "each surface retains a source address",
        ),
        check(
            "reconciliation:artifact-paths",
            ServiceReleasePlane.ARTIFACT,
            len({item.relative_path for item in snapshot.artifacts}) == len(snapshot.artifacts),
            len({item.relative_path for item in snapshot.artifacts}),
            len(snapshot.artifacts),
            "artifact paths remain unique for filesystem export",
        ),
        check(
            "reconciliation:gate-state",
            ServiceReleasePlane.GATE,
            all(item.passed for item in snapshot.gates) == snapshot.accepted,
            all(item.passed for item in snapshot.gates),
            snapshot.accepted,
            "aggregate acceptance follows the gate partition",
        ),
    ]
    accepted = all(item.passed for item in checks)
    body = {"bundle_id": snapshot.bundle_id, "checks": checks, "accepted": accepted}
    return ServiceReleaseReconciliation(
        snapshot.bundle_id,
        tuple(checks),
        accepted,
        content_hash(body, prefix="service-release-reconciliation"),
    )


def build_service_release_summary(
    snapshot: ServiceReleaseSnapshot,
    source_snapshot: ServiceSurfaceSnapshot,
) -> ServiceReleaseSummary:
    """Build human-readable counters that retain both source and registry totals."""

    counts = service_release_snapshot_counts(snapshot)
    counters = tuple(
        sorted(
            {
                **{key: int(value) for key, value in counts.items() if key != "accepted"},
                "source_capability_count": len(source_snapshot.capability_report.certificates),
                "source_program_domain_count": len(source_snapshot.program_runtime.report.receipts),
                "source_operational_artifact_count": len(source_snapshot.operational_trace.artifacts),
                "source_program_release_domain_count": len(source_snapshot.program_release.domains),
                "source_program_release_artifact_count": len(source_snapshot.program_release.artifacts),
            }.items()
        )
    )
    surfaces = tuple(
        {
            "surface_id": item.surface_id,
            "category": item.category,
            "row_count": item.row_count,
            "artifact_count": item.artifact_count,
            "accepted": item.accepted,
            "content_address": item.content_address,
        }
        for item in snapshot.surfaces
    )
    body = {
        "bundle_id": snapshot.bundle_id,
        "counters": counters,
        "surfaces": surfaces,
        "accepted": snapshot.accepted,
    }
    return ServiceReleaseSummary(
        snapshot.bundle_id,
        counters,
        surfaces,
        snapshot.accepted,
        content_hash(body, prefix="service-release-summary"),
    )


def audit_service_release_summary(
    summary: ServiceReleaseSummary,
    source_snapshot: ServiceSurfaceSnapshot,
) -> ServiceReleaseSummaryAudit:
    """Check summary counters against both fixed and source denominators."""

    values = summary.counter_map
    pairs = (
        ("surface_count", SERVICE_RELEASE_SURFACE_COUNT),
        ("artifact_count", SERVICE_RELEASE_ARTIFACT_COUNT),
        ("dependency_count", SERVICE_RELEASE_DEPENDENCY_COUNT),
        ("gate_count", SERVICE_RELEASE_GATE_COUNT),
        ("source_capability_count", len(source_snapshot.capability_report.certificates)),
        ("source_program_domain_count", len(source_snapshot.program_runtime.report.receipts)),
        ("source_operational_artifact_count", len(source_snapshot.operational_trace.artifacts)),
        ("source_program_release_domain_count", len(source_snapshot.program_release.domains)),
        ("source_program_release_artifact_count", len(source_snapshot.program_release.artifacts)),
    )
    checks = tuple(
        check(
            f"summary:{key}",
            ServiceReleasePlane.RECONCILIATION,
            values.get(key) == expected,
            values.get(key),
            expected,
            f"summary counter {key} is conserved",
        )
        for key, expected in pairs
    ) + (
        check(
            "summary:accepted",
            ServiceReleasePlane.RECONCILIATION,
            summary.accepted,
            summary.accepted,
            True,
            "summary follows aggregate acceptance",
        ),
    )
    accepted = all(item.passed for item in checks)
    body = {"bundle_id": summary.bundle_id, "checks": checks, "accepted": accepted}
    return ServiceReleaseSummaryAudit(
        summary.bundle_id,
        checks,
        accepted,
        content_hash(body, prefix="service-release-summary-audit"),
    )


def export_service_release_summary_csv(summary: ServiceReleaseSummary) -> bytes:
    return csv_payload(({"counter": key, "value": value} for key, value in summary.counters))


def export_service_release_summary_markdown(summary: ServiceReleaseSummary) -> bytes:
    return markdown_payload(
        "Service release registry summary",
        ({"counter": key, "value": value} for key, value in summary.counters),
    )


__all__ = [
    "audit_service_release_summary",
    "build_service_release_summary",
    "export_service_release_summary_csv",
    "export_service_release_summary_markdown",
    "reconcile_service_release",
]
