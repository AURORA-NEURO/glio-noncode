"""Whole-product assurance summaries, status, and reconciliation checks."""

from __future__ import annotations

from .release_assurance_bundle import release_assurance_snapshot_counts
from .release_assurance_contracts import (
    RELEASE_ASSURANCE_CHECK_COUNT,
    RELEASE_ASSURANCE_DOMAIN_COUNT,
    RELEASE_ASSURANCE_EVIDENCE_LINK_COUNT,
    ReleaseAssurancePlane,
    ReleaseAssuranceSnapshot,
    ReleaseAssuranceSummary,
    ReleaseAssuranceSummaryAudit,
    check,
)
from .release_assurance_support import csv_payload, markdown_payload
from .serialization import content_hash


def build_release_assurance_summary(snapshot: ReleaseAssuranceSnapshot) -> ReleaseAssuranceSummary:
    """Build a compact source-independent denominator summary."""

    counts = release_assurance_snapshot_counts(snapshot)
    counters = tuple(
        sorted(
            {
                **{key: value for key, value in counts.items() if key != "accepted"},
                "failed_check_count": len(snapshot.checks) - snapshot.passed_check_count,
                "limitation_count": sum(len(item.limitations) for item in snapshot.domains),
            }.items()
        )
    )
    rows = tuple(
        {
            "domain_id": item.domain_id,
            "title": item.title,
            "denominator": item.denominator,
            "accepted_count": item.accepted_count,
            "readiness_percent": item.readiness_percent,
            "evidence_count": item.evidence_count,
            "accepted": item.accepted,
            "source_address": item.source_address,
        }
        for item in snapshot.domains
    )
    body = {
        "bundle_id": snapshot.bundle_id,
        "counters": counters,
        "domain_rows": rows,
        "overall_percent": snapshot.overall_percent,
        "accepted": snapshot.accepted,
    }
    return ReleaseAssuranceSummary(
        snapshot.bundle_id,
        counters,
        rows,
        snapshot.overall_percent,
        snapshot.accepted,
        content_hash(body, prefix="release-assurance-summary"),
    )


def audit_release_assurance_summary(
    summary: ReleaseAssuranceSummary,
    snapshot: ReleaseAssuranceSnapshot,
) -> ReleaseAssuranceSummaryAudit:
    """Independently reconcile summary counters and readiness percentages."""

    values = summary.counter_map
    checks = [
        check("summary:domain-count", "summary", ReleaseAssurancePlane.CROSS_PLANE,
              values.get("domain_count") == RELEASE_ASSURANCE_DOMAIN_COUNT,
              values.get("domain_count"), RELEASE_ASSURANCE_DOMAIN_COUNT,
              "summary retains all assurance domains", (snapshot.content_address,)),
        check("summary:evidence-count", "summary", ReleaseAssurancePlane.CROSS_PLANE,
              values.get("evidence_count") == RELEASE_ASSURANCE_EVIDENCE_LINK_COUNT,
              values.get("evidence_count"), RELEASE_ASSURANCE_EVIDENCE_LINK_COUNT,
              "summary retains all evidence links", (snapshot.content_address,)),
        check("summary:check-count", "summary", ReleaseAssurancePlane.CROSS_PLANE,
              values.get("check_count") == RELEASE_ASSURANCE_CHECK_COUNT,
              values.get("check_count"), RELEASE_ASSURANCE_CHECK_COUNT,
              "summary retains all assurance checks", (snapshot.content_address,)),
        check("summary:passed-count", "summary", ReleaseAssurancePlane.CROSS_PLANE,
              values.get("passed_check_count") == snapshot.passed_check_count,
              values.get("passed_check_count"), snapshot.passed_check_count,
              "summary passed checks match the snapshot", (snapshot.content_address,)),
        check("summary:overall-percent", "summary", ReleaseAssurancePlane.CROSS_PLANE,
              summary.overall_percent == snapshot.overall_percent,
              summary.overall_percent, snapshot.overall_percent,
              "summary carries the addressed readiness percentage", (snapshot.content_address,)),
        check("summary:domain-rows", "summary", ReleaseAssurancePlane.CROSS_PLANE,
              len(summary.domain_rows) == len(snapshot.domains),
              len(summary.domain_rows), len(snapshot.domains),
              "summary domain rows close the source domains", (snapshot.content_address,)),
        check("summary:accepted", "summary", ReleaseAssurancePlane.CROSS_PLANE,
              summary.accepted == snapshot.accepted,
              summary.accepted, snapshot.accepted,
              "summary acceptance follows the snapshot", (snapshot.content_address,)),
    ]
    accepted = all(item.passed for item in checks)
    body = {"bundle_id": summary.bundle_id, "checks": checks, "accepted": accepted}
    return ReleaseAssuranceSummaryAudit(
        summary.bundle_id,
        tuple(checks),
        accepted,
        content_hash(body, prefix="release-assurance-summary-audit"),
    )


def release_assurance_status(snapshot: ReleaseAssuranceSnapshot) -> dict[str, object]:
    """Return the compact product-readiness status used by health clients."""

    counts = release_assurance_snapshot_counts(snapshot)
    return {
        "service": "glio-noncode",
        "version": "release-assurance-v1",
        "bundle_id": snapshot.bundle_id,
        "run_id": snapshot.run_id,
        "content_address": snapshot.content_address,
        "accepted": snapshot.accepted,
        "overall_percent": snapshot.overall_percent,
        "domain_count": counts["domain_count"],
        "accepted_domain_count": counts["accepted_domain_count"],
        "check_count": counts["check_count"],
        "passed_check_count": counts["passed_check_count"],
        "failed_check_count": int(counts["check_count"]) - int(counts["passed_check_count"]),
        "evidence_count": counts["evidence_count"],
        "public_boundary": "aggregate-only",
    }


def export_release_assurance_summary_csv(summary: ReleaseAssuranceSummary) -> bytes:
    return csv_payload(({"counter": key, "value": value} for key, value in summary.counters))


def export_release_assurance_summary_markdown(summary: ReleaseAssuranceSummary) -> bytes:
    return markdown_payload(
        "Whole-product release assurance summary",
        ({"counter": key, "value": value} for key, value in summary.counters),
    )


__all__ = [
    "audit_release_assurance_summary",
    "build_release_assurance_summary",
    "export_release_assurance_summary_csv",
    "export_release_assurance_summary_markdown",
    "release_assurance_status",
]
