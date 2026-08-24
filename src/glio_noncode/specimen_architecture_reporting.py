"""Deterministic reports for the D03 specimen runtime."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Any

from .serialization import jsonable
from .specimen_architecture_contracts import (
    SpecimenArchitectureFixture,
    SpecimenArchitectureReviewQueue,
    SpecimenArchitectureRuntime,
    SpecimenArchitectureState,
    addressed,
)
from .specimen_architecture_depth import specimen_architecture_depth_percent
from .specimen_architecture_metrics import SpecimenArchitectureMetrics


@dataclass(frozen=True, slots=True)
class SpecimenArchitectureReport:
    fixture_id: str
    title: str
    state: SpecimenArchitectureState
    summary: dict[str, Any]
    sections: tuple[dict[str, Any], ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_specimen_architecture_report(
    fixture: SpecimenArchitectureFixture,
    runtime: SpecimenArchitectureRuntime,
    metrics: SpecimenArchitectureMetrics,
) -> SpecimenArchitectureReport:
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
        "depth_percent": specimen_architecture_depth_percent(
            fixture, runtime.evaluation
        ),
        "compliance_accepted": runtime.compliance.accepted,
        "positive_count": runtime.evaluation.positive_count,
        "control_count": runtime.evaluation.control_count,
        "validation_cells": metrics.validation_cell_count,
        "stage_count": len(runtime.stages),
        "artifact_count": len(runtime.artifacts),
        "release_state": runtime.release.state.value,
    }
    sections = (
        {
            "section_id": "sources",
            "title": "Public specimen sources",
            "rows": [item.to_dict() for item in fixture.sources],
        },
        {
            "section_id": "operations",
            "title": "Specimen operations",
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
        "title": "D03 Specimen Context and Release Architecture",
        "state": runtime.state,
        "summary": summary,
        "sections": sections,
    }
    return SpecimenArchitectureReport(
        fixture_id=fixture.fixture_id,
        title="D03 Specimen Context and Release Architecture",
        state=runtime.state,
        summary=summary,
        sections=sections,
        content_address=addressed(body, "specimen-report"),
    )


def render_specimen_architecture_markdown(report: SpecimenArchitectureReport) -> str:
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
        rows = section["rows"]
        lines.extend(("", f"## {section['title']}", ""))
        if not rows:
            lines.append("No rows.")
            continue
        keys = tuple(sorted({str(key) for row in rows for key in row}))
        lines.append("| " + " | ".join(key.replace("_", " ").title() for key in keys) + " |")
        lines.append("| " + " | ".join("---" for _ in keys) + " |")
        lines.extend(
            "| " + " | ".join(_value(row.get(key, "")) for key in keys) + " |"
            for row in rows
        )
    return "\n".join(lines) + "\n"


def specimen_architecture_receipts_csv(runtime: SpecimenArchitectureRuntime) -> str:
    rows = (
        (
            item.case_id,
            item.operation_id,
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
    return _csv(
        (
            "case_id",
            "operation_id",
            "expected_state",
            "observed_state",
            "expected_result_state",
            "observed_result_state",
            "expected_issue_codes",
            "observed_issue_codes",
            "passed",
            "output_address",
            "content_address",
        ),
        rows,
    )


def specimen_architecture_review_csv(queue: SpecimenArchitectureReviewQueue) -> str:
    rows = (
        (
            item.review_id,
            item.case_id,
            item.operation_id,
            item.priority,
            ";".join(item.reason_codes),
            item.disposition,
            item.next_action,
            item.content_address,
        )
        for item in queue.items
    )
    return _csv(
        (
            "review_id",
            "case_id",
            "operation_id",
            "priority",
            "reason_codes",
            "disposition",
            "next_action",
            "content_address",
        ),
        rows,
    )


def _csv(headers: tuple[str, ...], rows: Any) -> str:
    stream = io.StringIO(newline="")
    csv.writer(stream, lineterminator="\n").writerows((headers, *rows))
    return stream.getvalue()


def _value(value: Any) -> str:
    if isinstance(value, (tuple, list, dict)):
        value = jsonable(value)
    return str(value).replace("|", "\\|").replace("\n", " ")


__all__ = [
    "SpecimenArchitectureReport",
    "build_specimen_architecture_report",
    "render_specimen_architecture_markdown",
    "specimen_architecture_receipts_csv",
    "specimen_architecture_review_csv",
]
