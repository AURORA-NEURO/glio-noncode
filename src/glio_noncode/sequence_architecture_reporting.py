"""Deterministic D06 Markdown and CSV reports."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Any

from .sequence_architecture_contracts import (
    SequenceArchitectureFixture,
    SequenceArchitectureReviewQueue,
    SequenceArchitectureRuntime,
    SequenceArchitectureState,
    addressed,
)
from .sequence_architecture_data_dictionary import SequenceArchitectureDataDictionary
from .sequence_architecture_depth import sequence_architecture_depth_percent
from .sequence_architecture_metrics import SequenceArchitectureMetrics
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class SequenceArchitectureReport:
    fixture_id: str
    title: str
    state: SequenceArchitectureState
    summary: dict[str, Any]
    sections: tuple[dict[str, Any], ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_sequence_architecture_report(
    fixture: SequenceArchitectureFixture,
    runtime: SequenceArchitectureRuntime,
    metrics: SequenceArchitectureMetrics,
    dictionary: SequenceArchitectureDataDictionary,
) -> SequenceArchitectureReport:
    summary = {
        "boundary": fixture.boundary,
        "context_key": fixture.context_key,
        "source_count": len(fixture.sources),
        "operation_count": len(fixture.operations),
        "case_count": len(fixture.cases),
        "evaluation_checks": len(runtime.evaluation.checks),
        "quality_checks": len(runtime.quality.checks),
        "result_state_count": metrics.state_count,
        "issue_code_count": metrics.issue_code_count,
        "depth_percent": sequence_architecture_depth_percent(
            fixture, runtime.evaluation
        ),
        "compliance_accepted": runtime.compliance.accepted,
        "positive_count": runtime.evaluation.positive_count,
        "control_count": runtime.evaluation.control_count,
        "validation_cells": metrics.validation_cell_count,
        "stage_count": len(runtime.stages),
        "artifact_count": len(runtime.artifacts),
        "dictionary_field_count": len(dictionary.fields),
        "release_state": runtime.release.state.value,
    }
    sections = (
        {
            "section_id": "sources",
            "title": "Public sequence sources",
            "rows": [item.to_dict() for item in fixture.sources],
        },
        {
            "section_id": "operations",
            "title": "Sequence operations",
            "rows": [item.to_dict() for item in fixture.operations],
        },
        {
            "section_id": "controls",
            "title": "Held controls",
            "rows": [item.to_dict() for item in runtime.review_queue.items],
        },
        {
            "section_id": "artifacts",
            "title": "Release artifacts",
            "rows": [item.to_dict() for item in runtime.artifacts],
        },
    )
    body = {
        "fixture_id": fixture.fixture_id,
        "title": "D06 Sequence Grammar and Variant Effect Architecture",
        "state": runtime.state,
        "summary": summary,
        "sections": sections,
    }
    return SequenceArchitectureReport(
        fixture_id=fixture.fixture_id,
        title="D06 Sequence Grammar and Variant Effect Architecture",
        state=runtime.state,
        summary=summary,
        sections=sections,
        content_address=addressed(body, "sequence-report"),
    )


def render_sequence_architecture_markdown(report: SequenceArchitectureReport) -> str:
    lines = [
        f"# {report.title}",
        "",
        f"- Fixture: `{report.fixture_id}`",
        f"- State: `{report.state.value}`",
        f"- Address: `{report.content_address}`",
        "",
        "## Summary",
        "",
        "| Measure | Value |",
        "| --- | ---: |",
    ]
    lines.extend(
        f"| {key.replace('_', ' ').title()} | {_value(value)} |"
        for key, value in report.summary.items()
    )
    for section in report.sections:
        lines.extend(("", f"## {section['title']}", ""))
        rows = section["rows"]
        if not rows:
            lines.append("No rows.")
            continue
        keys = tuple(sorted({str(key) for row in rows for key in row}))
        lines.append("| " + " | ".join(key.replace("_", " ").title() for key in keys) + " |")
        lines.append("| " + " | ".join("---" for _ in keys) + " |")
        lines.extend(
            "| " + " | ".join(_value(row.get(key, "")) for key in keys) + " |" for row in rows
        )
    return "\n".join(lines) + "\n"


def sequence_architecture_receipts_csv(runtime: SequenceArchitectureRuntime) -> str:
    headers = (
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
    rows = (
        (
            item.case_id,
            item.operation_id,
            item.family.value,
            item.expected_state.value,
            item.observed_state.value,
            item.expected_result_state,
            item.observed_result_state,
            ";".join(item.expected_issue_codes),
            ";".join(item.observed_issue_codes),
            item.passed,
            item.output_address,
            item.content_address,
        )
        for item in runtime.evaluation.receipts
    )
    return _csv(headers, rows)


def sequence_architecture_review_csv(queue: SequenceArchitectureReviewQueue) -> str:
    headers = (
        "review_id",
        "case_id",
        "operation_id",
        "scenario",
        "priority",
        "reason_codes",
        "disposition",
        "next_action",
        "content_address",
    )
    rows = (
        (
            item.review_id,
            item.case_id,
            item.operation_id,
            item.scenario.value,
            item.priority,
            ";".join(item.reason_codes),
            item.disposition,
            item.next_action,
            item.content_address,
        )
        for item in queue.items
    )
    return _csv(headers, rows)


def _csv(headers: tuple[str, ...], rows: Any) -> str:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return stream.getvalue()


def _value(value: Any) -> str:
    if isinstance(value, (tuple, list, dict)):
        value = jsonable(value)
    return str(value).replace("|", "\\|").replace("\n", " ")


__all__ = [
    "SequenceArchitectureReport",
    "build_sequence_architecture_report",
    "render_sequence_architecture_markdown",
    "sequence_architecture_receipts_csv",
    "sequence_architecture_review_csv",
]
