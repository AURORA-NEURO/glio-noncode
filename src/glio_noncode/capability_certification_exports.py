"""Public projections for capability certification reports."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from .capability_certification import (
    capability_certification_domain_matrix,
    capability_certification_percent,
)
from .capability_certification_contracts import CapabilityCertificationReport
from .serialization import jsonable


def export_capability_certification_json(report: CapabilityCertificationReport) -> str:
    """Serialize a complete report with row receipts and all checks."""

    return json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"


def export_capability_certification_summary_json(report: CapabilityCertificationReport) -> str:
    """Serialize a compact dashboard projection."""

    body = {
        "report_id": report.report_id,
        "catalog_version": report.catalog_version,
        "catalog_address": report.catalog_address,
        "report_address": report.content_address,
        "state": report.state.value,
        "accepted": report.accepted,
        "capability_count": report.capability_count,
        "total_checks": report.total_checks,
        "passed_checks": report.passed_checks,
        "failed_checks": report.failed_checks,
        "certification_percent": capability_certification_percent(report),
        "domains": list(capability_certification_domain_matrix(report)),
    }
    return json.dumps(body, indent=2, sort_keys=True) + "\n"


def export_capability_certification_csv(report: CapabilityCertificationReport) -> str:
    """Export one stable row per certified capability."""

    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        (
            "capability_id",
            "domain_id",
            "domain",
            "layer",
            "capability_order",
            "capability",
            "kind",
            "release_wave",
            "mvp_64",
            "registry_state",
            "state",
            "implementation_count",
            "implementation_resolved",
            "test_count",
            "test_resolved",
            "failed_checks",
            "content_address",
        )
    )
    for item in report.certificates:
        writer.writerow(
            (
                item.capability_id,
                item.domain_id,
                item.domain,
                item.layer,
                item.capability_order,
                item.capability,
                item.kind,
                item.release_wave,
                str(item.mvp_64).lower(),
                item.registry_state,
                item.state.value,
                item.implementation_count,
                item.implementation_resolved,
                item.test_count,
                item.test_resolved,
                item.failed_checks,
                item.content_address,
            )
        )
    return output.getvalue()


def export_capability_certification_checks_csv(report: CapabilityCertificationReport) -> str:
    """Export global and row-level check receipts for machine review."""

    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("scope", "capability_id", "check_id", "category", "passed", "observed", "required", "detail", "content_address"))
    checks: list[tuple[str, Any]] = [("global", item) for item in report.checks]
    checks.extend(("capability", item) for certificate in report.certificates for item in certificate.checks)
    for scope, item in checks:
        writer.writerow(
            (
                scope,
                item.capability_id,
                item.check_id,
                item.category.value,
                str(item.passed).lower(),
                json.dumps(jsonable(item.observed), sort_keys=True),
                json.dumps(jsonable(item.required), sort_keys=True),
                item.detail,
                item.content_address,
            )
        )
    return output.getvalue()


def export_capability_certification_domains_csv(report: CapabilityCertificationReport) -> str:
    """Export one row per domain for dashboards and release summaries."""

    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("domain_id", "domain", "capability_count", "mvp_count", "accepted_count", "review_count", "blocked_count", "readiness_percent", "implementation_references", "test_references", "failed_checks", "content_address"))
    for item in report.domain_summaries:
        writer.writerow((item.domain_id, item.domain, item.capability_count, item.mvp_count, item.accepted_count, item.review_count, item.blocked_count, item.readiness_percent, item.implementation_references, item.test_references, item.failed_checks, item.content_address))
    return output.getvalue()


def render_capability_certification_markdown(report: CapabilityCertificationReport) -> str:
    """Render a detailed human review document with all domain totals."""

    lines = [
        "# Capability certification",
        "",
        f"- Report: `{report.report_id}`",
        f"- State: `{report.state.value}`",
        f"- Catalog: `{report.catalog_address}`",
        f"- Report address: `{report.content_address}`",
        f"- Capabilities: `{report.capability_count}`",
        f"- Checks: `{report.passed_checks}/{report.total_checks}` passed",
        f"- Readiness: `{capability_certification_percent(report):.2f}%`",
        "",
        "## Domain readiness",
        "",
        "| Domain | Capabilities | MVP | Accepted | Review | Implementation refs | Test refs | Readiness |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    lines.extend(
        f"| {item.domain_id} {item.domain} | {item.capability_count} | {item.mvp_count} | {item.accepted_count} | {item.review_count} | {item.implementation_references} | {item.test_references} | {item.readiness_percent:.2f}% |"
        for item in report.domain_summaries
    )
    lines.extend(("", "## Global checks", "", "| Check | Result | Detail |", "|---|---|---|"))
    lines.extend(f"| `{item.check_id}` | {'pass' if item.passed else 'fail'} | {item.detail} |" for item in report.checks)
    lines.extend(("", "## Row-level failures", ""))
    failures = [item for certificate in report.certificates for item in certificate.checks if not item.passed]
    if failures:
        lines.append("| Capability | Check | Observed | Required |")
        lines.append("|---|---|---|---|")
        lines.extend(f"| `{item.capability_id}` | `{item.check_id}` | `{item.observed}` | `{item.required}` |" for item in failures)
    else:
        lines.append("No row-level failures.")
    return "\n".join(lines) + "\n"


__all__ = [
    "export_capability_certification_checks_csv",
    "export_capability_certification_csv",
    "export_capability_certification_domains_csv",
    "export_capability_certification_json",
    "export_capability_certification_summary_json",
    "render_capability_certification_markdown",
]
