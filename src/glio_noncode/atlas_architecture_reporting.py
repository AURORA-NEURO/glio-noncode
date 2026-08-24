"""Human-readable and tabular reports for the D05 atlas runtime."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Any

from .atlas_architecture_contracts import (
    AtlasArchitectureFixture,
    AtlasArchitectureReviewQueue,
    AtlasArchitectureRuntime,
    AtlasArchitectureState,
    addressed,
)
from .atlas_architecture_data_dictionary import AtlasArchitectureDataDictionary
from .atlas_architecture_depth import atlas_architecture_depth_percent
from .atlas_architecture_metrics import AtlasArchitectureMetrics
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class AtlasArchitectureReport:
    fixture_id: str
    title: str
    state: AtlasArchitectureState
    summary: dict[str, Any]
    sections: tuple[dict[str, Any], ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_atlas_architecture_report(
    fixture: AtlasArchitectureFixture,
    runtime: AtlasArchitectureRuntime,
    metrics: AtlasArchitectureMetrics,
    dictionary: AtlasArchitectureDataDictionary,
) -> AtlasArchitectureReport:
    """Assemble a release report without embedding input payloads."""

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
        "depth_percent": atlas_architecture_depth_percent(
            fixture, runtime.evaluation
        ),
        "compliance_accepted": runtime.compliance.accepted,
        "positive_count": runtime.evaluation.positive_count,
        "control_count": runtime.evaluation.control_count,
        "accepted_receipts": sum(
            item.observed_state is AtlasArchitectureState.ACCEPTED
            for item in runtime.evaluation.receipts
        ),
        "review_receipts": sum(
            item.observed_state is AtlasArchitectureState.REVIEW
            for item in runtime.evaluation.receipts
        ),
        "validation_cells": metrics.validation_cell_count,
        "stage_count": len(runtime.stages),
        "artifact_count": len(runtime.artifacts),
        "dictionary_field_count": len(dictionary.fields),
        "release_state": runtime.release.state.value,
    }
    sections = (
        {
            "section_id": "provenance",
            "title": "Public provenance",
            "rows": [
                {
                    "source_id": source.source_id,
                    "family": source.family.value,
                    "title": source.title,
                    "uri": source.uri,
                    "version": source.version,
                    "license": source.license,
                }
                for source in fixture.sources
            ],
        },
        {
            "section_id": "operations",
            "title": "Operation closure",
            "rows": [
                {
                    "operation_id": operation.operation_id,
                    "capability_id": operation.capability_id,
                    "ordinal": operation.ordinal,
                    "family": operation.family.value,
                    "plane": operation.plane.value,
                    "dependencies": operation.dependencies,
                }
                for operation in fixture.operations
            ],
        },
        {
            "section_id": "review",
            "title": "Held boundary",
            "rows": [item.to_dict() for item in runtime.review_queue.items],
        },
        {
            "section_id": "release",
            "title": "Release artifacts",
            "rows": [item.to_dict() for item in runtime.artifacts],
        },
    )
    body = {
        "fixture_id": fixture.fixture_id,
        "title": "D05 Glioma Regulatory Atlas Architecture",
        "state": runtime.state,
        "summary": summary,
        "sections": sections,
    }
    return AtlasArchitectureReport(
        fixture_id=fixture.fixture_id,
        title="D05 Glioma Regulatory Atlas Architecture",
        state=runtime.state,
        summary=summary,
        sections=sections,
        content_address=addressed(body, "atlas-report"),
    )


def render_atlas_architecture_markdown(report: AtlasArchitectureReport) -> str:
    """Render a deterministic report suitable for a release attachment."""

    lines = [
        f"# {report.title}",
        "",
        f"- Fixture: `{report.fixture_id}`",
        f"- State: `{report.state.value}`",
        f"- Report address: `{report.content_address}`",
        "",
        "## Summary",
        "",
        "| Measure | Value |",
        "| --- | ---: |",
    ]
    lines.extend(
        f"| {key.replace('_', ' ').title()} | {value} |" for key, value in report.summary.items()
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
        for row in rows:
            values = [_markdown_value(row.get(key, "")) for key in keys]
            lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines) + "\n"


def atlas_architecture_receipts_csv(runtime: AtlasArchitectureRuntime) -> str:
    """Export all 64 receipts with controls and positive rows distinguishable."""

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
            item.expected_counts.get("primary", 0),
            item.observed_counts.get("primary", 0),
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
            "family",
            "expected_state",
            "observed_state",
            "expected_result_state",
            "observed_result_state",
            "expected_issue_codes",
            "observed_issue_codes",
            "expected_primary",
            "observed_primary",
            "passed",
            "output_address",
            "content_address",
        ),
        rows,
    )


def atlas_architecture_review_csv(queue: AtlasArchitectureReviewQueue) -> str:
    """Export the held-control queue as a stable review table."""

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
    return _csv(
        (
            "review_id",
            "case_id",
            "operation_id",
            "scenario",
            "priority",
            "reason_codes",
            "disposition",
            "next_action",
            "content_address",
        ),
        rows,
    )


def atlas_architecture_sources_csv(fixture: AtlasArchitectureFixture) -> str:
    """Export public source receipts without case payloads."""

    rows = (
        (
            item.source_id,
            item.family.value,
            item.title,
            item.uri,
            item.version,
            item.scope,
            item.license,
            item.content_address,
        )
        for item in fixture.sources
    )
    return _csv(
        ("source_id", "family", "title", "uri", "version", "scope", "license", "content_address"),
        rows,
    )


def _csv(headers: tuple[str, ...], rows: Any) -> str:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return stream.getvalue()


def _markdown_value(value: Any) -> str:
    if isinstance(value, (tuple, list, dict)):
        value = jsonable(value)
    return str(value).replace("|", "\\|").replace("\n", " ")


__all__ = [
    "AtlasArchitectureReport",
    "atlas_architecture_receipts_csv",
    "atlas_architecture_review_csv",
    "atlas_architecture_sources_csv",
    "build_atlas_architecture_report",
    "render_atlas_architecture_markdown",
]
