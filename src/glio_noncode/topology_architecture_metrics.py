"""Topology aggregate coverage and receipt metrics."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .topology_architecture_contracts import (
    TopologyArchitectureEvaluation,
    TopologyArchitectureFixture,
    addressed,
)


def topology_architecture_metrics(
    fixture: TopologyArchitectureFixture, evaluation: TopologyArchitectureEvaluation | None = None
) -> dict[str, Any]:
    metrics = {
        "fixture_id": fixture.fixture_id,
        "source_count": len(fixture.sources),
        "operation_count": len(fixture.operations),
        "case_count": len(fixture.cases),
        "positive_count": len(fixture.positive_cases),
        "control_count": len(fixture.control_cases),
        "scenario_counts": dict(
            sorted(Counter(item.scenario.value for item in fixture.cases).items())
        ),
        "family_counts": dict(sorted(Counter(item.family.value for item in fixture.cases).items())),
        "plane_counts": dict(sorted(Counter(item.plane.value for item in fixture.cases).items())),
        "state_counts": dict(
            sorted(Counter(item.observed_result_state for item in evaluation.executions).items())
        )
        if evaluation
        else {},
        "issue_counts": dict(
            sorted(
                Counter(
                    issue for item in evaluation.executions for issue in item.issue_codes
                ).items()
            )
        )
        if evaluation
        else {},
        "evaluation_accepted": evaluation.accepted if evaluation else None,
        "check_count": len(evaluation.checks) if evaluation else 0,
        "receipt_pass_rate": sum(item.passed for item in evaluation.receipts)
        / len(evaluation.receipts)
        if evaluation and evaluation.receipts
        else None,
    }
    return metrics | {"content_address": addressed(metrics, "topology-metrics")}


def topology_architecture_metric_invariants(metrics: dict[str, Any]) -> tuple[str, ...]:
    failures: list[str] = []
    for key, expected in (
        ("source_count", 17),
        ("operation_count", 16),
        ("case_count", 64),
        ("positive_count", 16),
        ("control_count", 48),
        ("check_count", 458),
    ):
        if metrics.get(key) != expected:
            failures.append(key)
    if metrics.get("scenario_counts") != {
        "foreign_context": 16,
        "identity_conflict": 16,
        "malformed_input": 16,
        "positive": 16,
    }:
        failures.append("scenario_counts")
    return tuple(failures)


__all__ = ["topology_architecture_metric_invariants", "topology_architecture_metrics"]
