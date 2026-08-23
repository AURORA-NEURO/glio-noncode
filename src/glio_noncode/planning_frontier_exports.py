"""Stable tabular exports for reviewer queues."""

from __future__ import annotations

import csv
import io
from typing import Any

from .planning_frontier_contracts import PlanningEvaluation


def export_planning_review_csv(evaluation: PlanningEvaluation) -> str:
    stream = io.StringIO()
    fields = ("record_id", "operation", "role", "expected_state", "observed_state", "issue_codes", "content_address")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in evaluation.executions:
        writer.writerow({
            "record_id": item.record_id,
            "operation": item.operation.value,
            "role": item.role.value,
            "expected_state": item.expected_state.value,
            "observed_state": item.observed_state.value,
            "issue_codes": "|".join(item.issue_codes),
            "content_address": item.content_address,
        })
    return stream.getvalue()


__all__ = ["export_planning_review_csv"]
