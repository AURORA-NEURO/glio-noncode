"""JSON, CSV, and Markdown projections for review consumers."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from .validation_beta_frontier_fixture_eval import ValidationBetaFrontierEvaluation


def export_validation_beta_frontier_json(payload: Any) -> str:
    value = payload.to_dict() if hasattr(payload, "to_dict") else payload
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def export_validation_beta_frontier_review_csv(evaluation: ValidationBetaFrontierEvaluation) -> str:
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("record_id", "operation", "expected_state", "observed_state", "accepted", "issue_codes"))
    for row in evaluation.rows:
        writer.writerow((row.record_id, row.operation.value, row.expected_state, row.observed_state, str(row.accepted).lower(), ";".join(row.observed_issue_codes)))
    return output.getvalue()


def render_validation_beta_frontier_markdown(evaluation: ValidationBetaFrontierEvaluation) -> str:
    lines = ["# Validation-beta frontier review", "", "| Record | Operation | State | Accepted |", "|---|---|---|---|"]
    lines.extend(f"| {row.record_id} | {row.operation.value} | {row.observed_state} | {'yes' if row.accepted else 'no'} |" for row in evaluation.rows)
    lines.extend(("", "This is a bounded research-planning projection. It is not an efficacy, safety, causal, clinical, or execution claim."))
    return "\n".join(lines) + "\n"


__all__ = ["export_validation_beta_frontier_json", "export_validation_beta_frontier_review_csv", "render_validation_beta_frontier_markdown"]
