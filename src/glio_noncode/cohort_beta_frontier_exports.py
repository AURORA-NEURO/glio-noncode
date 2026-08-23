"""Stable JSON, CSV, and Markdown projections for downstream review."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from .cohort_beta_frontier_fixture_eval import CohortBetaFrontierEvaluation
from .cohort_beta_frontier_review import CohortBetaFrontierReviewQueue


def export_cohort_beta_frontier_json(evaluation: CohortBetaFrontierEvaluation) -> str:
    return json.dumps(evaluation.to_dict(), sort_keys=True, indent=2)


def export_cohort_beta_frontier_review_csv(queue: CohortBetaFrontierReviewQueue) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=("record_id", "operation", "priority", "disposition", "reason"), lineterminator="\n")
    writer.writeheader()
    for item in queue.items:
        writer.writerow({"record_id": item.record_id, "operation": item.operation, "priority": item.priority, "disposition": item.disposition, "reason": item.reason})
    return output.getvalue()


def render_cohort_beta_frontier_review_markdown(queue: CohortBetaFrontierReviewQueue) -> str:
    lines = ["# C05-C08 review queue", "", "| Operation | Record | Priority | Disposition |", "|---|---|---:|---|"]
    lines.extend(f"| {item.operation} | {item.record_id} | {item.priority} | {item.disposition} |" for item in queue.items)
    return "\n".join(lines) + "\n"


__all__ = ["export_cohort_beta_frontier_json", "export_cohort_beta_frontier_review_csv", "render_cohort_beta_frontier_review_markdown"]
