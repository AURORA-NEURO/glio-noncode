"""Coverage and quality metrics for Domain 08 C01-C04."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_frontier_fixture_eval import CellContextFrontierEvaluation
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextFrontierMetric:
    metric_id: str
    value: float
    required: float
    passed: bool
    unit: str
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.metric_id or not self.unit or not self.detail:
            raise ValidationError("cell metric is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextFrontierMetrics:
    metrics: tuple[CellContextFrontierMetric, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.metrics:
            raise ValidationError("cell metrics are empty")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def failed_metric_ids(self) -> tuple[str, ...]:
        return tuple(item.metric_id for item in self.metrics if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_metric_ids": list(self.failed_metric_ids)}


def build_cell_context_frontier_metrics(
    evaluation: CellContextFrontierEvaluation,
) -> CellContextFrontierMetrics:
    positive = len(evaluation.positive_rows)
    supported = sum(item.observed_state == "supported" for item in evaluation.positive_rows)
    metrics = (
        CellContextFrontierMetric(
            "positive_support_rate",
            supported / positive if positive else 0.0,
            1.0,
            supported == positive == 4,
            "ratio",
            "all positive context paths must support",
        ),
        CellContextFrontierMetric(
            "state_match_rate",
            evaluation.state_match_count / len(evaluation.records),
            1.0,
            evaluation.state_match_count == 16,
            "ratio",
            "expected and observed states must match",
        ),
        CellContextFrontierMetric(
            "issue_floor_rate",
            evaluation.issue_match_count / len(evaluation.records),
            1.0,
            evaluation.issue_match_count == 16,
            "ratio",
            "expected parser issue floors must match",
        ),
        CellContextFrontierMetric(
            "operation_coverage",
            len({item.operation for item in evaluation.records}) / 4,
            1.0,
            len({item.operation for item in evaluation.records}) == 4,
            "ratio",
            "four context operations must execute",
        ),
        CellContextFrontierMetric(
            "receipt_rate",
            sum(item.adapter.content_address.startswith("sha256:") for item in evaluation.records)
            / len(evaluation.records),
            1.0,
            all(item.adapter.content_address.startswith("sha256:") for item in evaluation.records),
            "ratio",
            "every adapter result must have a receipt",
        ),
        CellContextFrontierMetric(
            "ambiguity_visibility",
            sum(item.observed_state == "ambiguous" for item in evaluation.control_rows),
            1.0,
            any(item.observed_state == "ambiguous" for item in evaluation.control_rows),
            "rows",
            "ambiguous candidate paths remain visible",
        ),
        CellContextFrontierMetric(
            "contradiction_visibility",
            sum(item.observed_state == "contradictory" for item in evaluation.control_rows),
            1.0,
            any(item.observed_state == "contradictory" for item in evaluation.control_rows),
            "rows",
            "conflicting age evidence remains visible",
        ),
        CellContextFrontierMetric(
            "foreign_visibility",
            sum(item.observed_state == "out_of_domain" for item in evaluation.control_rows),
            1.0,
            any(item.observed_state == "out_of_domain" for item in evaluation.control_rows),
            "rows",
            "foreign context remains refused",
        ),
        CellContextFrontierMetric(
            "partial_visibility",
            sum(item.observed_state == "partial" for item in evaluation.control_rows),
            1.0,
            any(item.observed_state == "partial" for item in evaluation.control_rows),
            "rows",
            "malformed input remains partial",
        ),
        CellContextFrontierMetric(
            "abstention_visibility",
            sum(item.observed_state == "abstained" for item in evaluation.control_rows),
            1.0,
            any(item.observed_state == "abstained" for item in evaluation.control_rows),
            "rows",
            "missing dimension remains abstained",
        ),
    )
    return CellContextFrontierMetrics(metrics, all(item.passed for item in metrics))


__all__ = [
    "CellContextFrontierMetric",
    "CellContextFrontierMetrics",
    "build_cell_context_frontier_metrics",
]
