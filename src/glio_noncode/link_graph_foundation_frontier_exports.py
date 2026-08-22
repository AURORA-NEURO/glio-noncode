"""Stable export formats for the C01-C04 review surface."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation
from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierFixture
from .link_graph_foundation_frontier_review_queue import LinkGraphFoundationFrontierReviewQueue


def export_link_graph_foundation_frontier_payload(value: Any) -> str:
    payload = value.to_dict() if hasattr(value, "to_dict") else value
    return json.dumps(payload, sort_keys=True, indent=2)


def export_link_graph_foundation_frontier_manifest(fixture: LinkGraphFoundationFrontierFixture, evaluation: LinkGraphFoundationFrontierEvaluation) -> str:
    return export_link_graph_foundation_frontier_payload({"fixture": fixture.to_dict(False), "evaluation": evaluation.to_dict(False)})


def export_link_graph_foundation_frontier_review_csv(queue: LinkGraphFoundationFrontierReviewQueue) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=("record_id", "operation", "priority", "disposition", "state", "issue_codes"))
    writer.writeheader()
    for item in queue.entries:
        writer.writerow({"record_id": item.record_id, "operation": item.operation, "priority": item.priority, "disposition": item.disposition, "state": item.state, "issue_codes": ";".join(item.issue_codes)})
    return output.getvalue()


def render_link_graph_foundation_frontier_review_markdown(queue: LinkGraphFoundationFrontierReviewQueue) -> str:
    lines = ["# Link graph foundation review", "", "| Record | Operation | Priority | Disposition | State | Issues |", "|---|---|---:|---|---|---|"]
    lines.extend(f"| {item.record_id} | {item.operation} | {item.priority} | {item.disposition} | {item.state} | {', '.join(item.issue_codes) or 'none'} |" for item in queue.entries)
    return "\n".join(lines) + "\n"


__all__ = ["export_link_graph_foundation_frontier_manifest", "export_link_graph_foundation_frontier_payload", "export_link_graph_foundation_frontier_review_csv", "render_link_graph_foundation_frontier_review_markdown"]
