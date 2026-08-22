"""Sanitized review exports for context-alpha results."""

from __future__ import annotations

import csv
import io
import json

from .cell_context_alpha_frontier_fixture_eval import CellContextAlphaFrontierEvaluation
from .cell_context_alpha_frontier_public_data import CellContextAlphaFrontierFixture


def export_cell_context_alpha_frontier_manifest(
    fixture: CellContextAlphaFrontierFixture, evaluation: CellContextAlphaFrontierEvaluation
) -> str:
    return json.dumps(
        {"fixture": fixture.to_dict(False), "evaluation": evaluation.to_dict()},
        sort_keys=True,
        indent=2,
    )


def export_cell_context_alpha_frontier_review_csv(
    evaluation: CellContextAlphaFrontierEvaluation,
) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=(
            "record_id",
            "operation",
            "role",
            "expected_state",
            "observed_state",
            "state_matches",
            "issue_codes",
            "result_count",
            "candidate_ids",
        ),
    )
    writer.writeheader()
    for row in evaluation.records:
        writer.writerow(
            {
                "record_id": row.record_id,
                "operation": row.operation,
                "role": row.role,
                "expected_state": row.record.expected_state.value,
                "observed_state": row.observed_state,
                "state_matches": row.state_matches,
                "issue_codes": ";".join(row.observed_issue_codes),
                "result_count": row.adapter.measurements.get("result_count", 0),
                "candidate_ids": ";".join(row.adapter.measurements.get("candidate_ids", ())),
            }
        )
    return output.getvalue()


def render_cell_context_alpha_frontier_review_markdown(
    evaluation: CellContextAlphaFrontierEvaluation,
) -> str:
    lines = [
        "# Domain 08 context-alpha review",
        "",
        "| Record | Operation | Expected | Observed | Review |",
        "|---|---|---|---|---|",
    ]
    for row in evaluation.records:
        review = "pass" if row.state_matches and row.issue_floor_matches else "review"
        lines.append(
            "| "
            f"{row.record_id} | {row.operation} | {row.record.expected_state.value} | "
            f"{row.observed_state} | {review} |"
        )
    return "\n".join(lines) + "\n"


__all__ = [
    "export_cell_context_alpha_frontier_manifest",
    "export_cell_context_alpha_frontier_review_csv",
    "render_cell_context_alpha_frontier_review_markdown",
]
