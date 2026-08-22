"""Deterministic operational metrics for the sequence-effect frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sequence_effect_frontier_fixture_eval import SequenceEffectEvaluation
from .sequence_effect_frontier_public_data import SequenceEffectOperation, SequenceEffectState
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceEffectOperationMetric:
    operation: SequenceEffectOperation
    total: int
    accepted: int
    review: int
    issue_count: int
    state_counts: dict[str, int]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "operation": self.operation,
                        "total": self.total,
                        "accepted": self.accepted,
                        "review": self.review,
                        "issue_count": self.issue_count,
                        "state_counts": self.state_counts,
                    }
                ),
            )

    @property
    def acceptance_rate(self) -> float:
        return round(self.accepted / max(1, self.total), 6)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "operation": self.operation.value,
            "acceptance_rate": self.acceptance_rate,
        }


@dataclass(frozen=True, slots=True)
class SequenceEffectMetrics:
    total_records: int
    positive_records: int
    control_records: int
    accepted_records: int
    review_records: int
    operation_metrics: tuple[SequenceEffectOperationMetric, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "total_records": self.total_records,
                        "positive_records": self.positive_records,
                        "control_records": self.control_records,
                        "accepted_records": self.accepted_records,
                        "review_records": self.review_records,
                        "operation_metrics": self.operation_metrics,
                    }
                ),
            )

    @property
    def issue_rate(self) -> float:
        return round(self.review_records / max(1, self.total_records), 6)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_records": self.total_records,
            "positive_records": self.positive_records,
            "control_records": self.control_records,
            "accepted_records": self.accepted_records,
            "review_records": self.review_records,
            "issue_rate": self.issue_rate,
            "operation_metrics": [item.to_dict() for item in self.operation_metrics],
            "content_address": self.content_address,
        }


def compute_sequence_effect_metrics(evaluation: SequenceEffectEvaluation) -> SequenceEffectMetrics:
    operation_metrics: list[SequenceEffectOperationMetric] = []
    for operation in SequenceEffectOperation:
        rows = tuple(item for item in evaluation.executions if item.operation is operation)
        state_counts = {
            state.value: sum(item.adapter_state is state for item in rows)
            for state in SequenceEffectState
            if any(item.adapter_state is state for item in rows)
        }
        operation_metrics.append(
            SequenceEffectOperationMetric(
                operation,
                len(rows),
                sum(item.accepted for item in rows),
                sum(item.role.value == "control" for item in rows),
                sum(bool(item.issue_codes) for item in rows),
                state_counts,
            )
        )
    return SequenceEffectMetrics(
        total_records=len(evaluation.executions),
        positive_records=evaluation.positive_count,
        control_records=evaluation.control_count,
        accepted_records=sum(item.accepted for item in evaluation.executions),
        review_records=sum(bool(item.issue_codes) for item in evaluation.executions),
        operation_metrics=tuple(operation_metrics),
    )


__all__ = [
    "SequenceEffectMetrics",
    "SequenceEffectOperationMetric",
    "compute_sequence_effect_metrics",
]
