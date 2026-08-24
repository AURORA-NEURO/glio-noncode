"""Human- and machine-readable reporting for D07."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Any

from .chromatin_architecture_contracts import ChromatinArchitectureRuntime, addressed
from .chromatin_architecture_data_dictionary import ChromatinArchitectureDataDictionary
from .chromatin_architecture_depth import chromatin_architecture_depth_percent
from .chromatin_architecture_metrics import ChromatinArchitectureMetrics
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureReport:
    fixture_id: str
    release_id: str
    accepted: bool
    operation_count: int
    source_count: int
    case_count: int
    receipt_count: int
    check_count: int
    quality_check_count: int
    positive_count: int
    control_count: int
    stage_count: int
    artifact_ids: tuple[str, ...]
    operation_counts: dict[str, int]
    family_counts: dict[str, int]
    result_state_counts: dict[str, int]
    dictionary_field_count: int
    depth_percent: float
    compliance_accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_chromatin_architecture_report(
    runtime: ChromatinArchitectureRuntime,
    metrics: ChromatinArchitectureMetrics,
    dictionary: ChromatinArchitectureDataDictionary,
) -> ChromatinArchitectureReport:
    fixture = runtime.fixture
    evaluation = runtime.evaluation
    body = {
        "fixture_id": fixture.fixture_id,
        "release_id": runtime.release.release_id,
        "accepted": runtime.accepted,
        "operation_count": len(fixture.operations),
        "source_count": len(fixture.sources),
        "case_count": len(fixture.cases),
        "receipt_count": len(evaluation.receipts),
        "check_count": len(evaluation.checks),
        "quality_check_count": len(runtime.quality.checks),
        "positive_count": evaluation.positive_count,
        "control_count": evaluation.control_count,
        "stage_count": len(runtime.stages),
        "artifact_ids": tuple(item.artifact_id for item in runtime.artifacts),
        "operation_counts": metrics.operation_counts,
        "family_counts": metrics.family_counts,
        "result_state_counts": metrics.result_state_counts,
        "dictionary_field_count": len(dictionary.fields),
        "depth_percent": chromatin_architecture_depth_percent(runtime.depth),
        "compliance_accepted": runtime.compliance.accepted,
    }
    return ChromatinArchitectureReport(**body, content_address=addressed(body, "chromatin-report"))


def render_chromatin_architecture_markdown(report: ChromatinArchitectureReport) -> str:
    lines = [
        "# D07 Chromatin Architecture Report",
        "",
        f"- Fixture: `{report.fixture_id}`",
        f"- Release: `{report.release_id}`",
        f"- Accepted: `{str(report.accepted).lower()}`",
        f"- Sources: {report.source_count}",
        f"- Operations: {report.operation_count}",
        f"- Cases: {report.case_count} ({report.positive_count} positive, "
        f"{report.control_count} controls)",
        f"- Receipts: {report.receipt_count}",
        f"- Evaluation checks: {report.check_count}",
        f"- Quality checks: {report.quality_check_count}",
        f"- Runtime stages: {report.stage_count}",
        f"- Depth: {report.depth_percent}%",
        f"- Data-dictionary fields: {report.dictionary_field_count}",
        "",
        "## Family coverage",
        "",
        "| Family | Receipt count |",
        "| --- | ---: |",
    ]
    lines.extend(
        f"| {family} | {count} |" for family, count in sorted(report.family_counts.items())
    )
    lines.extend(("", "## Result states", "", "| State | Count |", "| --- | ---: |"))
    lines.extend(
        f"| {state} | {count} |" for state, count in sorted(report.result_state_counts.items())
    )
    lines.extend(
        (
            "",
        "This report retains descriptive measurements, uncertainty, source identity, "
        "and control routing. It does not establish clinical or causal conclusions.",
            "",
        )
    )
    return "\n".join(lines)


def chromatin_architecture_receipts_csv(runtime: ChromatinArchitectureRuntime) -> str:
    output = io.StringIO()
    fields = (
        "case_id",
        "operation_id",
        "family",
        "expected_state",
        "observed_state",
        "expected_result_state",
        "observed_result_state",
        "expected_issue_codes",
        "observed_issue_codes",
        "passed",
        "output_address",
        "content_address",
    )
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in runtime.evaluation.receipts:
        writer.writerow(
            {
                "case_id": item.case_id,
                "operation_id": item.operation_id,
                "family": item.family.value,
                "expected_state": item.expected_state.value,
                "observed_state": item.observed_state.value,
                "expected_result_state": item.expected_result_state,
                "observed_result_state": item.observed_result_state,
                "expected_issue_codes": ";".join(item.expected_issue_codes),
                "observed_issue_codes": ";".join(item.observed_issue_codes),
                "passed": str(item.passed).lower(),
                "output_address": item.output_address,
                "content_address": item.content_address,
            }
        )
    return output.getvalue()


def chromatin_architecture_review_csv(runtime: ChromatinArchitectureRuntime) -> str:
    output = io.StringIO()
    fields = (
        "case_id",
        "operation_id",
        "scenario",
        "priority",
        "blocking",
        "reason",
        "required_action",
        "content_address",
    )
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in runtime.review_queue.items:
        writer.writerow(
            {
                "case_id": item.case_id,
                "operation_id": item.operation_id,
                "scenario": item.scenario.value,
                "priority": item.priority,
                "blocking": str(item.blocking).lower(),
                "reason": item.reason,
                "required_action": item.required_action,
                "content_address": item.content_address,
            }
        )
    return output.getvalue()


__all__ = [
    "ChromatinArchitectureReport",
    "build_chromatin_architecture_report",
    "chromatin_architecture_receipts_csv",
    "chromatin_architecture_review_csv",
    "render_chromatin_architecture_markdown",
]
