"""Summary and tabular report builders for C09-C12 release consumers."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_regulation_frontier_fixture_eval import SequenceRegulationEvaluation
from .sequence_regulation_frontier_public_data import (
    SequenceRegulationFixture,
    SequenceRegulationOperation,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceRegulationReportMetric:
    metric_id: str
    label: str
    value: int | float | str
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.metric_id or not self.label or not self.detail:
            raise ValidationError("report metric is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceRegulationOperationSummary:
    operation: str
    record_count: int
    positive_count: int
    control_count: int
    accepted_count: int
    states: dict[str, int]
    issue_codes: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.operation or self.record_count < 1:
            raise ValidationError("operation summary is invalid")
        if self.positive_count + self.control_count != self.record_count:
            raise ValidationError("operation role counts do not add up")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceRegulationSummary:
    fixture_id: str
    context_key: str
    record_count: int
    positive_count: int
    control_count: int
    accepted_count: int
    review_count: int
    metrics: tuple[SequenceRegulationReportMetric, ...]
    operations: tuple[SequenceRegulationOperationSummary, ...]
    result_addresses: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.fixture_id or not self.context_key or not self.metrics or not self.operations:
            raise ValidationError("summary is incomplete")
        if self.positive_count + self.control_count != self.record_count:
            raise ValidationError("summary role counts do not add up")
        if len(self.result_addresses) != self.record_count:
            raise ValidationError("summary receipt count does not match records")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def operation_ids(self) -> tuple[str, ...]:
        return tuple(item.operation for item in self.operations)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceRegulationReceiptRow:
    record_id: str
    operation: str
    role: str
    state: str
    issue_codes: str
    result_address: str
    release_allowed: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _operation_summary(
    operation: SequenceRegulationOperation,
    evaluation: SequenceRegulationEvaluation,
) -> SequenceRegulationOperationSummary:
    rows = tuple(item for item in evaluation.records if item.adapter.operation is operation)
    states: dict[str, int] = {}
    issues: set[str] = set()
    for item in rows:
        states[item.observed_state.value] = states.get(item.observed_state.value, 0) + 1
        issues.update(item.observed_issue_codes)
    return SequenceRegulationOperationSummary(
        operation.value,
        len(rows),
        sum(item.role == "positive" for item in rows),
        sum(item.role == "control" for item in rows),
        sum(item.accepted for item in rows),
        states,
        tuple(sorted(issues)),
    )


def build_sequence_regulation_summary(
    fixture: SequenceRegulationFixture,
    evaluation: SequenceRegulationEvaluation,
) -> SequenceRegulationSummary:
    """Build a compact summary without dropping record-level receipts."""

    metrics = (
        SequenceRegulationReportMetric(
            "record_count", "Records", len(evaluation.records), "all positive and control rows"
        ),
        SequenceRegulationReportMetric(
            "positive_count", "Positive rows", evaluation.positive_count, "declared positive paths"
        ),
        SequenceRegulationReportMetric(
            "control_count", "Control rows", evaluation.control_count, "declared boundary paths"
        ),
        SequenceRegulationReportMetric(
            "accepted_count",
            "Accepted rows",
            sum(item.accepted for item in evaluation.records),
            "expected state and issue path matched",
        ),
        SequenceRegulationReportMetric(
            "review_count",
            "Review rows",
            sum(not item.accepted for item in evaluation.records),
            "rows held outside release",
        ),
        SequenceRegulationReportMetric(
            "operation_count",
            "Operations",
            len(SequenceRegulationOperation),
            "declared C09-C12 operation set",
        ),
        SequenceRegulationReportMetric(
            "receipt_count", "Receipts", len(evaluation.records), "one result receipt per record"
        ),
    )
    operations = tuple(
        _operation_summary(operation, evaluation) for operation in SequenceRegulationOperation
    )
    return SequenceRegulationSummary(
        fixture.fixture_id,
        fixture.context_key,
        len(evaluation.records),
        evaluation.positive_count,
        evaluation.control_count,
        sum(item.accepted for item in evaluation.records),
        sum(not item.accepted for item in evaluation.records),
        metrics,
        operations,
        tuple(item.adapter.content_address for item in evaluation.records),
        evaluation.accepted,
    )


def build_sequence_regulation_receipt_rows(
    evaluation: SequenceRegulationEvaluation,
    release_allowed: dict[str, bool] | None = None,
) -> tuple[SequenceRegulationReceiptRow, ...]:
    """Build a stable row set for CSV or table consumers."""

    release_allowed = release_allowed or {}
    return tuple(
        SequenceRegulationReceiptRow(
            item.record_id,
            item.adapter.operation.value,
            item.role,
            item.observed_state.value,
            ";".join(item.observed_issue_codes),
            item.adapter.content_address,
            release_allowed.get(
                item.record_id, item.observed_state.value == "supported" and item.accepted
            ),
        )
        for item in evaluation.records
    )


def render_sequence_regulation_metrics_csv(summary: SequenceRegulationSummary) -> str:
    """Render summary metrics as deterministic CSV."""

    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer, fieldnames=("metric_id", "label", "value", "detail"), lineterminator="\n"
    )
    writer.writeheader()
    for metric in summary.metrics:
        writer.writerow(
            {
                "metric_id": metric.metric_id,
                "label": metric.label,
                "value": metric.value,
                "detail": metric.detail,
            }
        )
    return buffer.getvalue()


def render_sequence_regulation_receipts_csv(
    rows: tuple[SequenceRegulationReceiptRow, ...],
) -> str:
    """Render record receipts as deterministic CSV."""

    buffer = io.StringIO(newline="")
    fields = (
        "record_id",
        "operation",
        "role",
        "state",
        "issue_codes",
        "result_address",
        "release_allowed",
    )
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row.to_dict())
    return buffer.getvalue()


def render_sequence_regulation_summary_markdown(summary: SequenceRegulationSummary) -> str:
    """Render a concise human-readable release summary."""

    lines = [
        "# Sequence regulation frontier summary",
        "",
        f"- Fixture: `{summary.fixture_id}`",
        f"- Context: `{summary.context_key}`",
        f"- Accepted: `{str(summary.accepted).lower()}`",
        (
            f"- Records: `{summary.record_count}` (`{summary.positive_count}` positive, "
            f"`{summary.control_count}` control)"
        ),
        f"- Review rows: `{summary.review_count}`",
        "",
        "| Operation | Records | Positive | Control | Accepted | States |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    lines.extend(
        (
            f"| `{item.operation}` | {item.record_count} | {item.positive_count} | "
            f"{item.control_count} | {item.accepted_count} | "
            f"{', '.join(f'{key}={value}' for key, value in sorted(item.states.items()))} |"
        )
        for item in summary.operations
    )
    lines.extend(("", "Every row remains available through its content-addressed receipt."))
    return "\n".join(lines) + "\n"


def verify_sequence_regulation_summary(
    summary: SequenceRegulationSummary,
) -> tuple[str, ...]:
    """Return stable summary failure IDs for release review."""

    failures: list[str] = []
    if len(summary.operations) != len(SequenceRegulationOperation):
        failures.append("operation_count")
    if set(summary.operation_ids) != {operation.value for operation in SequenceRegulationOperation}:
        failures.append("operation_ids")
    if any(not address.startswith("sha256:") for address in summary.result_addresses):
        failures.append("receipt_addresses")
    if summary.accepted_count + summary.review_count != summary.record_count:
        failures.append("row_counts")
    if any(item.record_count < 1 for item in summary.operations):
        failures.append("empty_operation")
    return tuple(failures)


__all__ = [
    "SequenceRegulationOperationSummary",
    "SequenceRegulationReceiptRow",
    "SequenceRegulationReportMetric",
    "SequenceRegulationSummary",
    "build_sequence_regulation_receipt_rows",
    "build_sequence_regulation_summary",
    "render_sequence_regulation_metrics_csv",
    "render_sequence_regulation_receipts_csv",
    "render_sequence_regulation_summary_markdown",
    "verify_sequence_regulation_summary",
]
