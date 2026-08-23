"""Stable JSON, CSV, and Markdown exports."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from .serialization import jsonable
from .validation_release_frontier_contracts import ValidationReleaseEvaluation
from .validation_release_frontier_summary import ValidationReleaseSummary


def export_validation_release_json(value: Any) -> str:
    return json.dumps(jsonable(value), indent=2, sort_keys=True) + "\n"


def export_validation_release_review_csv(evaluation: ValidationReleaseEvaluation) -> str:
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=("record_id", "operation", "role", "state", "issue_codes"))
    writer.writeheader()
    for item in evaluation.executions:
        writer.writerow({"record_id": item.record_id, "operation": item.operation.value, "role": item.role.value, "state": item.observed_state.value, "issue_codes": "|".join(item.issue_codes)})
    return stream.getvalue()


def export_validation_release_report_markdown(summary: ValidationReleaseSummary) -> str:
    lines = ["# Validation Release Frontier Report", "", f"- Fixture: `{summary.fixture_id}`", f"- Release: `{summary.release_id}`", f"- Accepted: `{str(summary.accepted).lower()}`", f"- Checks: `{summary.passed_checks}/{summary.check_count}`", "", "## State counts", ""]
    lines.extend(f"- `{key}`: {value}" for key, value in sorted(summary.state_counts.items()))
    lines.extend(("", "## Issue counts", ""))
    lines.extend(f"- `{key}`: {value}" for key, value in sorted(summary.issue_counts.items()))
    return "\n".join(lines) + "\n"


__all__ = ["export_validation_release_json", "export_validation_release_report_markdown", "export_validation_release_review_csv"]
