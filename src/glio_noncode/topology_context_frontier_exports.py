"""Sanitized topology review exports."""

from __future__ import annotations

import csv
import io
import json

from .topology_context_frontier_fixture_eval import TopologyContextFrontierEvaluation
from .topology_context_frontier_public_data import TopologyContextFrontierFixture


def export_topology_context_frontier_manifest(
    fixture: TopologyContextFrontierFixture,
    evaluation: TopologyContextFrontierEvaluation,
) -> str:
    payload = {
        "fixture": {
            "fixture_id": fixture.fixture_id,
            "version": fixture.version,
            "boundary": fixture.boundary,
            "content_address": fixture.content_address,
        },
        "evaluation": {
            "accepted": evaluation.accepted,
            "state_match_count": evaluation.state_match_count,
            "issue_match_count": evaluation.issue_match_count,
            "content_address": evaluation.content_address,
        },
        "rows": [
            {
                "record_id": item.record_id,
                "operation": item.operation,
                "role": item.role,
                "state": item.observed_state,
                "result_address": item.adapter.content_address,
            }
            for item in evaluation.rows
        ],
    }
    return json.dumps(payload, sort_keys=True, indent=2)


def export_topology_context_frontier_review_csv(
    evaluation: TopologyContextFrontierEvaluation,
) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(("record_id", "operation", "role", "state", "issue_count", "result_address"))
    for item in evaluation.rows:
        writer.writerow(
            (
                item.record_id,
                item.operation,
                item.role,
                item.observed_state,
                len(item.observed_issue_codes),
                item.adapter.content_address,
            )
        )
    return output.getvalue()


def render_topology_context_frontier_review_markdown(
    evaluation: TopologyContextFrontierEvaluation,
) -> str:
    lines = [
        "# Domain 09 topology context review",
        "",
        f"Accepted: `{evaluation.accepted}`",
        "",
        "| Record | Operation | State | Issues |",
        "|---|---|---|---:|",
    ]
    lines.extend(
        f"| {item.record_id} | {item.operation} | {item.observed_state} | "
        f"{len(item.observed_issue_codes)} |"
        for item in evaluation.rows
    )
    return "\n".join(lines) + "\n"


__all__ = [
    "export_topology_context_frontier_manifest",
    "export_topology_context_frontier_review_csv",
    "render_topology_context_frontier_review_markdown",
]
