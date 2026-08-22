"""Stable JSON, CSV, and Markdown exports for sequence grammar review."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from .sequence_grammar_frontier_fixture_eval import SequenceGrammarEvaluation
from .sequence_grammar_frontier_metrics import SequenceGrammarMetrics
from .sequence_grammar_frontier_public_data import SequenceGrammarFixture
from .sequence_grammar_frontier_quality_gate import SequenceGrammarQualityReport
from .sequence_grammar_frontier_views import SequenceGrammarView
from .serialization import content_hash, jsonable


def export_sequence_grammar_json(value: Any) -> str:
    payload = value.to_dict() if hasattr(value, "to_dict") else jsonable(value)
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _csv_text(fieldnames: tuple[str, ...], rows: list[dict[str, Any]]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def export_sequence_grammar_receipts_csv(evaluation: SequenceGrammarEvaluation) -> str:
    fields = ("record_id", "operation", "role", "state", "issue_codes", "result_address")
    rows = [
        {
            "record_id": item.record_id,
            "operation": item.operation.value,
            "role": item.role.value,
            "state": item.adapter_state.value,
            "issue_codes": ";".join(item.issue_codes),
            "result_address": item.content_address,
        }
        for item in evaluation.executions
    ]
    return _csv_text(fields, rows)


def export_sequence_grammar_review_csv(view: SequenceGrammarView) -> str:
    fields = (
        "record_id",
        "operation",
        "role",
        "state",
        "priority",
        "issue_codes",
        "review_action",
        "publishable",
        "result_address",
    )
    rows = [
        {
            "record_id": entry.record_id,
            "operation": entry.operation.value,
            "role": entry.role.value,
            "state": entry.state.value,
            "priority": entry.priority,
            "issue_codes": ";".join(entry.issue_codes),
            "review_action": entry.review_action,
            "publishable": str(entry.publishable).lower(),
            "result_address": entry.result_address,
        }
        for entry in view.entries
    ]
    return _csv_text(fields, rows)


def export_sequence_grammar_metrics_csv(metrics: SequenceGrammarMetrics) -> str:
    fields = (
        "operation",
        "total",
        "positive",
        "controls",
        "supported",
        "review",
        "invalid",
        "abstained",
        "issue_codes",
    )
    rows = [
        {
            "operation": item.operation.value,
            "total": item.total,
            "positive": item.positive,
            "controls": item.controls,
            "supported": item.supported,
            "review": item.review,
            "invalid": item.invalid,
            "abstained": item.abstained,
            "issue_codes": ";".join(f"{key}={value}" for key, value in item.issue_counts.items()),
        }
        for item in metrics.operation_metrics
    ]
    return _csv_text(fields, rows)


def render_sequence_grammar_review_markdown(view: SequenceGrammarView) -> str:
    lines = [
        f"# Sequence grammar review: `{view.fixture_id}`",
        "",
        f"Accepted: `{view.accepted}`",
        f"Review rows: `{view.review_count}`",
        "",
        "| Record | Operation | Role | State | Action |",
        "|---|---|---|---|---|",
    ]
    lines.extend(
        (
            f"| {entry.record_id} | {entry.operation.value} | {entry.role.value} | "
            f"{entry.state.value} | {entry.review_action} |"
        )
        for entry in view.entries
    )
    return "\n".join(lines) + "\n"


def render_sequence_grammar_release_markdown(
    fixture: SequenceGrammarFixture, quality: SequenceGrammarQualityReport
) -> str:
    return "\n".join(
        (
            f"# Sequence grammar beta release `{fixture.fixture_id}`",
            "",
            f"Quality accepted: `{quality.accepted}`",
            f"Evidence boundary: `{fixture.evidence_boundary}`",
            "",
            "This is research-only descriptive motif and grammar evidence; no calibrated "
            "probability or clinical interpretation is emitted.",
            "",
        )
    )


def sequence_grammar_export_receipt(export_name: str, text: str) -> dict[str, Any]:
    return {
        "export_name": export_name,
        "byte_count": len(text.encode("utf-8")),
        "content_address": content_hash(text),
        "format": "stable-text",
    }


__all__ = [
    "export_sequence_grammar_json",
    "export_sequence_grammar_metrics_csv",
    "export_sequence_grammar_receipts_csv",
    "export_sequence_grammar_review_csv",
    "render_sequence_grammar_release_markdown",
    "render_sequence_grammar_review_markdown",
    "sequence_grammar_export_receipt",
]
