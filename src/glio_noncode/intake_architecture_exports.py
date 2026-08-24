"""JSON, CSV, and Markdown projections for D02 review and release."""

from __future__ import annotations

import csv
import io
import json

from .intake_architecture_contracts import IntakeArchitectureRuntime
from .intake_architecture_depth import audit_intake_architecture_depth
from .intake_architecture_metrics import measure_intake_architecture
from .intake_architecture_review import intake_review_csv


def intake_architecture_runtime_json(runtime: IntakeArchitectureRuntime) -> str:
    return json.dumps(runtime.to_dict(), indent=2, sort_keys=True) + "\n"


def intake_architecture_quality_json(report) -> str:
    return json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"


def intake_architecture_evaluation_json(runtime: IntakeArchitectureRuntime) -> str:
    return json.dumps(runtime.evaluation.to_dict(), indent=2, sort_keys=True) + "\n"


def intake_architecture_compliance_json(runtime: IntakeArchitectureRuntime) -> str:
    return json.dumps(runtime.compliance.to_dict(), indent=2, sort_keys=True) + "\n"


def intake_architecture_receipts_csv(runtime: IntakeArchitectureRuntime) -> str:
    """Export one sanitized row per evaluation check for downstream review."""

    output = io.StringIO(newline="")
    fields = (
        "check_id",
        "case_id",
        "kind",
        "passed",
        "observed",
        "required",
        "detail",
        "content_address",
    )
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in runtime.evaluation.checks:
        writer.writerow(
            {
                "check_id": item.check_id,
                "case_id": item.case_id,
                "kind": item.kind.value,
                "passed": str(item.passed).lower(),
                "observed": json.dumps(item.observed, sort_keys=True),
                "required": json.dumps(item.required, sort_keys=True),
                "detail": item.detail,
                "content_address": item.content_address,
            }
        )
    return output.getvalue()


def intake_architecture_report_markdown(runtime: IntakeArchitectureRuntime) -> str:
    positive = sum(item.scenario.value == "positive" for item in runtime.evaluation.results)
    held = len(runtime.review_queue.items)
    metrics = measure_intake_architecture(runtime)
    depth = audit_intake_architecture_depth(runtime)
    compliance = runtime.compliance
    operation_rows = {item.operation_id: item for item in metrics.operation_metrics}
    lines = [
        "# D02 Variant Identity and Intake Architecture",
        "",
        "This report is a deterministic public-aggregate intake receipt and release gate.",
        "",
        f"- Runtime state: `{runtime.state.value}`",
        f"- Fixture: `{runtime.fixture_id}`",
        f"- Cases: `{len(runtime.evaluation.results)}` ({positive} positive, {held} held controls)",
        f"- Stages: `{len(runtime.stages)}`",
        f"- Evaluation checks: `{len(runtime.evaluation.checks)}`",
        f"- Compliance checks: `{len(compliance.checks) if compliance else 0}`",
        f"- Artifacts: `{len(runtime.artifacts)}` offline-capable",
        f"- Release: `{runtime.release.version}` / `{runtime.release.state.value}`",
        f"- Depth: `{depth.accepted}` with `{depth.receipt_count}` primitive receipts",
        "",
        "## Operation coverage",
        "",
        "| Operation | Cases | Accepted | Held | Receipts |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for operation_id in sorted(operation_rows):
        row = operation_rows[operation_id]
        lines.append(
            f"| `{operation_id}` | {row.total_cases} | {row.accepted_cases} | {row.held_cases} | {row.receipt_count} |"
        )
    lines.extend(
        (
            "",
            "## Runtime stages",
            "",
            "| Ordinal | Stage | State | Receipt |",
            "| ---: | --- | --- | --- |",
        )
    )
    lines.extend(
        f"| {stage.ordinal} | `{stage.stage_id}` | `{stage.state.value}` | `{stage.content_address}` |"
        for stage in runtime.stages
    )
    lines.extend(
        (
            "",
            "## Boundary",
            "",
            "No subject-level fields, external attribution metadata, or clinical interpretation are represented by this receipt.",
            "",
        )
    )
    return "\n".join(lines)


__all__ = [
    "intake_architecture_compliance_json",
    "intake_architecture_evaluation_json",
    "intake_architecture_quality_json",
    "intake_architecture_receipts_csv",
    "intake_architecture_report_markdown",
    "intake_architecture_runtime_json",
    "intake_review_csv",
]
