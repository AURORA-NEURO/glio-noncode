"""Quality gate for live capability certification."""

from __future__ import annotations

from typing import Any

from .capability_certification import (
    CAPABILITIES_PER_DOMAIN,
    CATALOG_CAPABILITY_COUNT,
    CATALOG_DOMAIN_COUNT,
    CATALOG_MVP_COUNT,
    CHECKS_PER_CAPABILITY,
    GLOBAL_CHECK_COUNT,
    capability_certification_percent,
)
from .capability_certification_contracts import (
    CapabilityCertificationQualityCheck,
    CapabilityCertificationQualityReport,
    CapabilityCertificationReport,
)
from .serialization import content_hash

QUALITY_CHECK_COUNT = 18


def _check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> CapabilityCertificationQualityCheck:
    body = {
        "check_id": check_id,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return CapabilityCertificationQualityCheck(
        **body,
        content_address=content_hash(body, prefix="capability-certification-quality-check"),
    )


def run_capability_certification_quality_gate(
    report: CapabilityCertificationReport,
) -> CapabilityCertificationQualityReport:
    """Close the publication gate for a live catalog certification."""

    checks = (
        _check("capability-denominator", report.capability_count == CATALOG_CAPABILITY_COUNT, report.capability_count, CATALOG_CAPABILITY_COUNT, "the quality gate uses all catalog capabilities"),
        _check("domain-denominator", len(report.domain_summaries) == CATALOG_DOMAIN_COUNT, len(report.domain_summaries), CATALOG_DOMAIN_COUNT, "the quality gate uses all catalog domains"),
        _check("capabilities-per-domain", all(item.capability_count == CAPABILITIES_PER_DOMAIN for item in report.domain_summaries), {item.domain_id: item.capability_count for item in report.domain_summaries}, {"each": CAPABILITIES_PER_DOMAIN}, "domain summaries conserve their row denominator"),
        _check("mvp-denominator", sum(item.mvp_count for item in report.domain_summaries) == CATALOG_MVP_COUNT, sum(item.mvp_count for item in report.domain_summaries), CATALOG_MVP_COUNT, "MVP coverage is conserved across domains"),
        _check("global-check-denominator", len(report.checks) == GLOBAL_CHECK_COUNT, len(report.checks), GLOBAL_CHECK_COUNT, "global certification checks have a fixed denominator"),
        _check("row-check-denominator", all(len(item.checks) == CHECKS_PER_CAPABILITY for item in report.certificates), {item.capability_id: len(item.checks) for item in report.certificates if len(item.checks) != CHECKS_PER_CAPABILITY}, CHECKS_PER_CAPABILITY, "each capability carries the complete row check plane"),
        _check("report-check-denominator", report.total_checks == CATALOG_CAPABILITY_COUNT * CHECKS_PER_CAPABILITY + GLOBAL_CHECK_COUNT, report.total_checks, CATALOG_CAPABILITY_COUNT * CHECKS_PER_CAPABILITY + GLOBAL_CHECK_COUNT, "row and global checks conserve the complete certification denominator"),
        _check("all-row-checks-pass", all(item.failed_checks == 0 for item in report.certificates), sum(item.failed_checks for item in report.certificates), 0, "every capability row passes its live checks"),
        _check("all-global-checks-pass", all(item.passed for item in report.checks), report.failed_checks, 0, "every global check passes"),
        _check("report-accepted", report.accepted, report.state.value, "accepted", "the underlying certification report is accepted"),
        _check("readiness-complete", capability_certification_percent(report) == 100.0, capability_certification_percent(report), 100.0, "all catalog rows are executable under current evidence"),
        _check("implementation-receipts-present", all(item.implementation_count > 0 for item in report.certificates), min(item.implementation_count for item in report.certificates), ">0", "each row carries implementation evidence"),
        _check("test-receipts-present", all(item.test_count > 0 for item in report.certificates), min(item.test_count for item in report.certificates), ">0", "each row carries test evidence"),
        _check("implementation-addresses", all(receipt.content_address for item in report.certificates for receipt in item.implementation_receipts), True, True, "implementation receipts are content-addressed"),
        _check("test-addresses", all(receipt.content_address for item in report.certificates for receipt in item.test_receipts), True, True, "test receipts are content-addressed"),
        _check("certificate-addresses", all(item.content_address.startswith("capability-certificate:") for item in report.certificates), True, True, "row certificates are content-addressed"),
        _check("summary-addresses", all(item.content_address.startswith("capability-domain-summary:") for item in report.domain_summaries), True, True, "domain summaries are content-addressed"),
        _check("report-address", report.content_address.startswith("capability-certification-report:"), report.content_address, "capability-certification-report:<digest>", "the complete report is content-addressed"),
    )
    accepted = all(item.passed for item in checks)
    body = {
        "report_address": report.content_address,
        "checks": checks,
        "accepted": accepted,
    }
    return CapabilityCertificationQualityReport(
        **body,
        content_address=content_hash(body, prefix="capability-certification-quality"),
    )


__all__ = [
    "QUALITY_CHECK_COUNT",
    "run_capability_certification_quality_gate",
]
