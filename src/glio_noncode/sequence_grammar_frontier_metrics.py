"""Conserved metrics for sequence grammar evaluations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_grammar_frontier_fixture_eval import SequenceGrammarEvaluation
from .sequence_grammar_frontier_public_data import SequenceGrammarOperation, SequenceGrammarState
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceGrammarOperationMetric:
    operation: SequenceGrammarOperation
    total: int
    positive: int
    controls: int
    supported: int
    review: int
    invalid: int
    abstained: int
    issue_counts: dict[str, int]
    content_address: str = ""

    def __post_init__(self) -> None:
        if self.total != self.positive + self.controls:
            raise ValidationError("operation metric role counts do not balance")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "operation": self.operation,
                        "total": self.total,
                        "positive": self.positive,
                        "controls": self.controls,
                        "supported": self.supported,
                        "review": self.review,
                        "invalid": self.invalid,
                        "abstained": self.abstained,
                        "issue_counts": self.issue_counts,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceGrammarMetrics:
    total_records: int
    positive_records: int
    control_records: int
    supported_records: int
    review_records: int
    invalid_records: int
    abstained_records: int
    operation_metrics: tuple[SequenceGrammarOperationMetric, ...]
    issue_counts: dict[str, int]
    evaluation_address: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if self.total_records != self.positive_records + self.control_records:
            raise ValidationError("overall role counts do not balance")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "total_records": self.total_records,
                        "positive_records": self.positive_records,
                        "control_records": self.control_records,
                        "supported_records": self.supported_records,
                        "review_records": self.review_records,
                        "invalid_records": self.invalid_records,
                        "abstained_records": self.abstained_records,
                        "operation_metrics": self.operation_metrics,
                        "issue_counts": self.issue_counts,
                        "evaluation_address": self.evaluation_address,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def compute_sequence_grammar_metrics(
    evaluation: SequenceGrammarEvaluation,
) -> SequenceGrammarMetrics:
    """Compute metrics without dropping controls or collapsing boundary states."""

    operation_metrics: list[SequenceGrammarOperationMetric] = []
    overall_issues: dict[str, int] = {}
    for operation in SequenceGrammarOperation:
        rows = tuple(item for item in evaluation.executions if item.operation is operation)
        issue_counts: dict[str, int] = {}
        for row in rows:
            for code in row.issue_codes:
                issue_counts[code] = issue_counts.get(code, 0) + 1
                overall_issues[code] = overall_issues.get(code, 0) + 1
        operation_metrics.append(
            SequenceGrammarOperationMetric(
                operation=operation,
                total=len(rows),
                positive=sum(row.role.value == "positive" for row in rows),
                controls=sum(row.role.value == "control" for row in rows),
                supported=sum(row.adapter_state is SequenceGrammarState.SUPPORTED for row in rows),
                review=sum(
                    row.adapter_state
                    in {SequenceGrammarState.PARTIAL, SequenceGrammarState.AMBIGUOUS}
                    for row in rows
                ),
                invalid=sum(row.adapter_state is SequenceGrammarState.INVALID for row in rows),
                abstained=sum(row.adapter_state is SequenceGrammarState.ABSTAINED for row in rows),
                issue_counts=dict(sorted(issue_counts.items())),
            )
        )
    return SequenceGrammarMetrics(
        total_records=len(evaluation.executions),
        positive_records=evaluation.positive_count,
        control_records=evaluation.control_count,
        supported_records=evaluation.supported_count,
        review_records=evaluation.review_count,
        invalid_records=evaluation.invalid_count,
        abstained_records=evaluation.abstained_count,
        operation_metrics=tuple(operation_metrics),
        issue_counts=dict(sorted(overall_issues.items())),
        evaluation_address=evaluation.content_address,
    )


__all__ = [
    "SequenceGrammarMetrics",
    "SequenceGrammarOperationMetric",
    "compute_sequence_grammar_metrics",
]
