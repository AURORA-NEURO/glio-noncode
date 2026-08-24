"""Deterministic operation, family, scenario, and issue metrics for D07."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from .chromatin_architecture_contracts import ChromatinArchitectureEvaluation, addressed
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureMetrics:
    fixture_id: str
    operation_counts: dict[str, int]
    family_counts: dict[str, int]
    scenario_counts: dict[str, int]
    observed_state_counts: dict[str, int]
    result_state_counts: dict[str, int]
    issue_code_counts: dict[str, int]
    positive_count: int
    control_count: int
    passed_receipt_count: int
    receipt_count: int
    check_count: int
    state_count: int
    issue_code_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def materialize_chromatin_architecture_metrics(
    evaluation: ChromatinArchitectureEvaluation,
) -> ChromatinArchitectureMetrics:
    operation_counts = Counter(item.operation_id for item in evaluation.receipts)
    family_counts = Counter(item.family.value for item in evaluation.receipts)
    scenario_counts = Counter(item.case_id.rsplit("-", 1)[-1] for item in evaluation.receipts)
    observed_state_counts = Counter(item.observed_state.value for item in evaluation.receipts)
    result_state_counts = Counter(item.observed_result_state for item in evaluation.receipts)
    issue_code_counts = Counter(
        code for item in evaluation.receipts for code in item.observed_issue_codes
    )
    body = {
        "fixture_id": evaluation.fixture_id,
        "operation_counts": dict(operation_counts),
        "family_counts": dict(family_counts),
        "scenario_counts": dict(scenario_counts),
        "observed_state_counts": dict(observed_state_counts),
        "result_state_counts": dict(result_state_counts),
        "issue_code_counts": dict(issue_code_counts),
        "positive_count": evaluation.positive_count,
        "control_count": evaluation.control_count,
        "passed_receipt_count": sum(item.passed for item in evaluation.receipts),
        "receipt_count": len(evaluation.receipts),
        "check_count": len(evaluation.checks),
        "state_count": len(result_state_counts),
        "issue_code_count": len(issue_code_counts),
    }
    return ChromatinArchitectureMetrics(
        fixture_id=evaluation.fixture_id,
        operation_counts=dict(operation_counts),
        family_counts=dict(family_counts),
        scenario_counts=dict(scenario_counts),
        observed_state_counts=dict(observed_state_counts),
        result_state_counts=dict(result_state_counts),
        issue_code_counts=dict(issue_code_counts),
        positive_count=evaluation.positive_count,
        control_count=evaluation.control_count,
        passed_receipt_count=sum(item.passed for item in evaluation.receipts),
        receipt_count=len(evaluation.receipts),
        check_count=len(evaluation.checks),
        state_count=len(result_state_counts),
        issue_code_count=len(issue_code_counts),
        content_address=addressed(body, "chromatin-metrics"),
    )


def chromatin_architecture_metrics_to_dict(metrics: ChromatinArchitectureMetrics) -> dict[str, Any]:
    return metrics.to_dict()


__all__ = [
    "ChromatinArchitectureMetrics",
    "chromatin_architecture_metrics_to_dict",
    "materialize_chromatin_architecture_metrics",
]
