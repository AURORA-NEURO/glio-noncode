"""Independent quality gate for the sixteen-domain program runtime."""

from __future__ import annotations

from typing import Any

from .program_runtime import PROGRAM_CHECKS_PER_DOMAIN, PROGRAM_DOMAIN_COUNT
from .program_runtime_contracts import (
    ArchitectureProgramReport,
    ProgramRuntimeQualityCheck,
    ProgramRuntimeQualityReport,
)
from .serialization import content_hash

PROGRAM_QUALITY_CHECK_COUNT = 18


def _check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ProgramRuntimeQualityCheck:
    body = {
        "check_id": check_id,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return ProgramRuntimeQualityCheck(
        **body,
        content_address=content_hash(body, prefix="architecture-program-quality-check"),
    )


def run_program_runtime_quality_gate(
    report: ArchitectureProgramReport,
) -> ProgramRuntimeQualityReport:
    """Reconcile denominator, resolution, execution, and public-boundary evidence."""

    checks = (
        _check(
            "domain-denominator",
            len(report.specs) == PROGRAM_DOMAIN_COUNT,
            len(report.specs),
            PROGRAM_DOMAIN_COUNT,
            "the program catalog contains all sixteen architecture domains",
        ),
        _check(
            "receipt-denominator",
            len(report.receipts) == PROGRAM_DOMAIN_COUNT,
            len(report.receipts),
            PROGRAM_DOMAIN_COUNT,
            "every architecture domain produces one normalized receipt",
        ),
        _check(
            "check-denominator",
            len(report.checks) == PROGRAM_DOMAIN_COUNT * PROGRAM_CHECKS_PER_DOMAIN + 12,
            len(report.checks),
            PROGRAM_DOMAIN_COUNT * PROGRAM_CHECKS_PER_DOMAIN + 12,
            "domain and global checks conserve the complete program denominator",
        ),
        _check(
            "domain-identities",
            tuple(item.domain_id for item in report.specs)
            == tuple(f"D{i:02d}" for i in range(1, PROGRAM_DOMAIN_COUNT + 1)),
            tuple(item.domain_id for item in report.specs),
            tuple(f"D{i:02d}" for i in range(1, PROGRAM_DOMAIN_COUNT + 1)),
            "specs retain canonical ordered domain identities",
        ),
        _check(
            "receipt-identities",
            tuple(item.domain_id for item in report.receipts)
            == tuple(f"D{i:02d}" for i in range(1, PROGRAM_DOMAIN_COUNT + 1)),
            tuple(item.domain_id for item in report.receipts),
            tuple(f"D{i:02d}" for i in range(1, PROGRAM_DOMAIN_COUNT + 1)),
            "receipts retain canonical ordered domain identities",
        ),
        _check(
            "all-checks-pass",
            report.failed_checks == 0,
            report.failed_checks,
            0,
            "all domain and global reconciliation checks pass",
        ),
        _check(
            "report-accepted",
            report.accepted,
            report.state.value,
            "accepted",
            "the normalized program report is accepted",
        ),
        _check(
            "fixture-resolution",
            all(item.fixture_resolution.startswith("resolved") for item in report.receipts),
            sum(item.fixture_resolution.startswith("resolved") for item in report.receipts),
            len(report.receipts),
            "all canonical fixture factories resolve",
        ),
        _check(
            "runtime-resolution",
            all(item.runtime_resolution.startswith("resolved") for item in report.receipts),
            sum(item.runtime_resolution.startswith("resolved") for item in report.receipts),
            len(report.receipts),
            "all canonical runtime functions resolve",
        ),
        _check(
            "runtime-acceptance",
            all(item.accepted for item in report.receipts),
            sum(item.accepted for item in report.receipts),
            len(report.receipts),
            "all domain runtimes reach acceptance",
        ),
        _check(
            "stage-receipts",
            all(item.stage_count > 0 for item in report.receipts),
            min((item.stage_count for item in report.receipts), default=0),
            ">0",
            "every domain runtime exposes ordered stages",
        ),
        _check(
            "evaluation-receipts",
            all(item.evaluation_check_count > 0 for item in report.receipts),
            min((item.evaluation_check_count for item in report.receipts), default=0),
            ">0",
            "every domain runtime exposes evaluation checks",
        ),
        _check(
            "artifact-receipts",
            all(item.artifact_count > 0 for item in report.receipts),
            min((item.artifact_count for item in report.receipts), default=0),
            ">0",
            "every domain runtime exposes release artifacts",
        ),
        _check(
            "issue-free-receipts",
            all(not item.issue_codes for item in report.receipts),
            {item.domain_id: list(item.issue_codes) for item in report.receipts if item.issue_codes},
            {},
            "normalized receipts contain no orchestration issue codes",
        ),
        _check(
            "fixture-addresses",
            all(":" in item.fixture_address for item in report.receipts),
            sum(":" in item.fixture_address for item in report.receipts),
            len(report.receipts),
            "all fixture outputs are content-addressed",
        ),
        _check(
            "runtime-addresses",
            all(":" in item.runtime_address for item in report.receipts),
            sum(":" in item.runtime_address for item in report.receipts),
            len(report.receipts),
            "all runtime outputs are content-addressed",
        ),
        _check(
            "public-boundary",
            all("private_projection_key" not in item.issue_codes for item in report.receipts),
            sum("private_projection_key" not in item.issue_codes for item in report.receipts),
            len(report.receipts),
            "all normalized runtime projections retain the public aggregate boundary",
        ),
        _check(
            "quality-address",
            report.content_address.startswith("architecture-program-report:"),
            report.content_address,
            "architecture-program-report:<digest>",
            "the complete program report is content-addressed",
        ),
    )
    accepted = all(item.passed for item in checks)
    body = {
        "report_address": report.content_address,
        "checks": checks,
        "accepted": accepted,
    }
    return ProgramRuntimeQualityReport(
        **body,
        content_address=content_hash(body, prefix="architecture-program-quality"),
    )


__all__ = ["PROGRAM_QUALITY_CHECK_COUNT", "run_program_runtime_quality_gate"]
