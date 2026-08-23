"""Deterministic coverage and acceptance metrics for D08."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .cell_state_architecture_contracts import (
    CellStateArchitectureEvaluation,
    CellStateArchitectureFixture,
    addressed,
)


def cell_state_architecture_metrics(
    fixture: CellStateArchitectureFixture, evaluation: CellStateArchitectureEvaluation | None = None
) -> dict[str, Any]:
    scenario_counts = Counter(item.scenario.value for item in fixture.cases)
    family_counts = Counter(item.family.value for item in fixture.cases)
    plane_counts = Counter(item.plane.value for item in fixture.cases)
    operation_counts = Counter(item.operation_id for item in fixture.cases)
    metrics = {
        "fixture_id": fixture.fixture_id,
        "source_count": len(fixture.sources),
        "operation_count": len(fixture.operations),
        "case_count": len(fixture.cases),
        "positive_count": len(fixture.positive_cases),
        "control_count": len(fixture.control_cases),
        "scenario_counts": dict(sorted(scenario_counts.items())),
        "family_counts": dict(sorted(family_counts.items())),
        "plane_counts": dict(sorted(plane_counts.items())),
        "case_counts_by_operation": dict(sorted(operation_counts.items())),
        "evaluation_accepted": evaluation.accepted if evaluation else None,
        "receipt_pass_rate": (
            sum(item.passed for item in evaluation.receipts) / len(evaluation.receipts)
        )
        if evaluation and evaluation.receipts
        else None,
    }
    return metrics | {"content_address": addressed(metrics, "cell-state-metrics")}


def metric_invariants(metrics: dict[str, Any]) -> tuple[str, ...]:
    failures: list[str] = []
    if metrics.get("source_count") != 18:
        failures.append("source_count")
    if metrics.get("operation_count") != 16:
        failures.append("operation_count")
    if metrics.get("case_count") != 64:
        failures.append("case_count")
    if metrics.get("scenario_counts") != {
        "foreign_context": 16,
        "identity_conflict": 16,
        "malformed_input": 16,
        "positive": 16,
    }:
        failures.append("scenario_counts")
    return tuple(failures)


__all__ = ["cell_state_architecture_metrics", "metric_invariants"]
