"""Stable JSON, CSV, and Markdown projections for sequence-effect operations."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from .sequence_effect_frontier_fixture_eval import SequenceEffectEvaluation
from .sequence_effect_frontier_metrics import SequenceEffectMetrics
from .sequence_effect_frontier_public_data import SequenceEffectFixture
from .sequence_effect_frontier_views import SequenceEffectView
from .serialization import content_hash


def export_sequence_effect_json(value: Any) -> str:
    payload = value.to_dict() if hasattr(value, "to_dict") else value
    return json.dumps(payload, sort_keys=True, indent=2) + "\n"


def export_sequence_effect_receipts_csv(evaluation: SequenceEffectEvaluation) -> str:
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("record_id", "operation", "role", "state", "issue_codes", "content_address"))
    for item in evaluation.executions:
        writer.writerow(
            (
                item.record_id,
                item.operation.value,
                item.role.value,
                item.adapter_state.value,
                "|".join(item.issue_codes),
                item.content_address,
            )
        )
    return output.getvalue()


def export_sequence_effect_review_csv(view: SequenceEffectView) -> str:
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        ("record_id", "operation", "role", "state", "priority", "action", "content_address")
    )
    for item in view.entries:
        writer.writerow(
            (
                item.record_id,
                item.operation,
                item.role,
                item.state,
                item.priority,
                item.action,
                item.content_address,
            )
        )
    return output.getvalue()


def export_sequence_effect_metrics_csv(metrics: SequenceEffectMetrics) -> str:
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        (
            "operation",
            "total",
            "accepted",
            "review",
            "issue_count",
            "acceptance_rate",
            "content_address",
        )
    )
    for item in metrics.operation_metrics:
        writer.writerow(
            (
                item.operation.value,
                item.total,
                item.accepted,
                item.review,
                item.issue_count,
                item.acceptance_rate,
                item.content_address,
            )
        )
    return output.getvalue()


def render_sequence_effect_review_markdown(view: SequenceEffectView) -> str:
    lines = [
        f"# Sequence effect review: {view.fixture_id}",
        "",
        f"Context: `{view.context_key}`",
        "",
        "| Record | Operation | Role | State | Priority | Action |",
        "|---|---|---|---|---:|---|",
    ]
    lines.extend(
        f"| {item.record_id} | {item.operation} | {item.role} | {item.state} | "
        f"{item.priority} | {item.action} |"
        for item in view.entries
    )
    return "\n".join(lines) + "\n"


def render_sequence_effect_release_markdown(fixture: SequenceEffectFixture, quality: Any) -> str:
    return (
        "\n".join(
            (
                f"# Sequence effect release: {fixture.fixture_id}",
                "",
                f"- Boundary: `{fixture.evidence_boundary}`",
                f"- Context: `{fixture.context_key}`",
                f"- Quality accepted: `{quality.accepted}`",
                f"- Quality address: `{quality.content_address}`",
                "- Model deltas remain non-probabilistic research evidence.",
            )
        )
        + "\n"
    )


def sequence_effect_export_receipt(export_name: str, text: str) -> dict[str, Any]:
    return {
        "export_name": export_name,
        "byte_count": len(text.encode("utf-8")),
        "content_address": content_hash(text),
    }


__all__ = [
    "export_sequence_effect_json",
    "export_sequence_effect_metrics_csv",
    "export_sequence_effect_receipts_csv",
    "export_sequence_effect_review_csv",
    "render_sequence_effect_release_markdown",
    "render_sequence_effect_review_markdown",
    "sequence_effect_export_receipt",
]
