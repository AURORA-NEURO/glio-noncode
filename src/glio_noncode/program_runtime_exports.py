"""Stable JSON, CSV, and Markdown projections for the program runtime."""

from __future__ import annotations

import csv
import io
import json

from .program_runtime import architecture_program_domain_matrix, architecture_program_percent
from .program_runtime_contracts import ArchitectureProgramReport, ProgramRuntime
from .serialization import jsonable


def architecture_program_report_json(report: ArchitectureProgramReport) -> str:
    return json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"


def architecture_program_summary_json(report: ArchitectureProgramReport) -> str:
    body = {
        "report_id": report.report_id,
        "report_address": report.content_address,
        "state": report.state.value,
        "accepted": report.accepted,
        "domain_count": len(report.receipts),
        "accepted_domain_count": sum(item.accepted for item in report.receipts),
        "certification_percent": architecture_program_percent(report),
        "check_count": len(report.checks),
        "passed_checks": report.passed_checks,
        "failed_checks": report.failed_checks,
        "total_stage_count": report.total_stage_count,
        "total_evaluation_check_count": report.total_evaluation_check_count,
        "total_artifact_count": report.total_artifact_count,
        "domains": list(architecture_program_domain_matrix(report)),
    }
    return json.dumps(body, indent=2, sort_keys=True) + "\n"


def architecture_program_runtime_json(runtime: ProgramRuntime) -> str:
    return json.dumps(runtime.to_dict(), indent=2, sort_keys=True) + "\n"


def architecture_program_receipts_csv(report: ArchitectureProgramReport) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        (
            "domain_id",
            "domain",
            "fixture_reference",
            "runtime_reference",
            "fixture_resolution",
            "runtime_resolution",
            "fixture_address",
            "runtime_address",
            "runtime_state",
            "accepted",
            "stage_count",
            "evaluation_check_count",
            "artifact_count",
            "issue_codes",
            "content_address",
        )
    )
    for item in report.receipts:
        writer.writerow(
            (
                item.domain_id,
                item.domain,
                item.fixture_reference,
                item.runtime_reference,
                item.fixture_resolution,
                item.runtime_resolution,
                item.fixture_address,
                item.runtime_address,
                item.runtime_state,
                str(item.accepted).lower(),
                item.stage_count,
                item.evaluation_check_count,
                item.artifact_count,
                ";".join(item.issue_codes),
                item.content_address,
            )
        )
    return output.getvalue()


def architecture_program_checks_csv(report: ArchitectureProgramReport) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        ("domain_id", "check_id", "category", "passed", "observed", "required", "detail", "content_address")
    )
    for item in report.checks:
        writer.writerow(
            (
                item.domain_id,
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


def architecture_program_domains_csv(report: ArchitectureProgramReport) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        (
            "domain_id",
            "domain",
            "accepted",
            "runtime_state",
            "stage_count",
            "evaluation_check_count",
            "artifact_count",
            "issue_codes",
            "runtime_address",
            "content_address",
        )
    )
    for item in architecture_program_domain_matrix(report):
        writer.writerow(
            (
                item["domain_id"],
                item["domain"],
                str(item["accepted"]).lower(),
                item["runtime_state"],
                item["stage_count"],
                item["evaluation_check_count"],
                item["artifact_count"],
                ";".join(item["issue_codes"]),
                item["runtime_address"],
                item["content_address"],
            )
        )
    return output.getvalue()


def architecture_program_report_markdown(report: ArchitectureProgramReport) -> str:
    lines = [
        "# Architecture program runtime",
        "",
        f"- State: `{report.state.value}`",
        f"- Report address: `{report.content_address}`",
        f"- Domains: `{len(report.receipts)}`",
        f"- Checks: `{report.passed_checks}/{len(report.checks)}` passed",
        f"- Domain readiness: `{architecture_program_percent(report):.2f}%`",
        "",
        "## Domain matrix",
        "",
        "| Domain | State | Stages | Evaluation checks | Artifacts | Runtime address |",
        "|---|---|---:|---:|---:|---|",
    ]
    lines.extend(
        f"| {item.domain_id} {item.domain} | {item.runtime_state} | {item.stage_count} | {item.evaluation_check_count} | {item.artifact_count} | `{item.runtime_address}` |"
        for item in report.receipts
    )
    lines.extend(("", "## Global checks", "", "| Check | Result | Detail |", "|---|---|---|"))
    lines.extend(
        f"| `{item.check_id}` | {'pass' if item.passed else 'fail'} | {item.detail} |"
        for item in report.checks
        if item.domain_id == "__program__"
    )
    return "\n".join(lines) + "\n"


__all__ = [
    "architecture_program_checks_csv",
    "architecture_program_domains_csv",
    "architecture_program_receipts_csv",
    "architecture_program_report_json",
    "architecture_program_report_markdown",
    "architecture_program_runtime_json",
    "architecture_program_summary_json",
]
