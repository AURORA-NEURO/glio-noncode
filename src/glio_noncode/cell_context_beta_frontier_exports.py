"""Sanitized JSON, CSV, and Markdown exports for beta review."""

from __future__ import annotations

import csv
import io
import json

from .cell_context_beta_frontier_fixture_eval import CellContextBetaFrontierEvaluation
from .cell_context_beta_frontier_public_data import CellContextBetaFrontierFixture


def export_cell_context_beta_frontier_manifest(
    fixture: CellContextBetaFrontierFixture, evaluation: CellContextBetaFrontierEvaluation
) -> str:
    return json.dumps(
        {"fixture": fixture.to_dict(False), "evaluation": evaluation.to_dict()},
        sort_keys=True,
        indent=2,
    )


def export_cell_context_beta_frontier_review_csv(
    evaluation: CellContextBetaFrontierEvaluation,
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
            "uncertainty",
            "selected_candidate_id",
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
                "uncertainty": row.adapter.measurements.get("uncertainty"),
                "selected_candidate_id": row.adapter.measurements.get("selected_candidate_id")
                or "",
            }
        )
    return output.getvalue()


def render_cell_context_beta_frontier_review_markdown(
    evaluation: CellContextBetaFrontierEvaluation,
) -> str:
    lines = [
        "# Domain 08 beta context prior review",
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
    "export_cell_context_beta_frontier_manifest",
    "export_cell_context_beta_frontier_review_csv",
    "render_cell_context_beta_frontier_review_markdown",
]
