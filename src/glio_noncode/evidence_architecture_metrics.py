"""State, scenario, family, operation, and issue metrics for D14."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .evidence_architecture_contracts import (
    EvidenceArchitectureEvaluation,
    EvidenceArchitectureFixture,
    addressed,
)
from .evidence_architecture_public_data import default_evidence_architecture_fixture


def evidence_architecture_metrics(
    fixture: EvidenceArchitectureFixture | None = None,
    evaluation: EvidenceArchitectureEvaluation | None = None,
) -> dict[str, Any]:
    selected = fixture or default_evidence_architecture_fixture()
    if evaluation is None:
        from .evidence_architecture_operations import evaluate_evidence_architecture_fixture

        evaluation = evaluate_evidence_architecture_fixture(selected)
    state_counts = Counter(item.observed_state.value for item in evaluation.executions)
    family_counts = Counter(item.family.value for item in evaluation.executions)
    operation_counts = Counter(item.operation.value for item in evaluation.executions)
    scenario_counts = Counter(item.scenario.value for item in evaluation.executions)
    issue_counts = Counter(
        issue for item in evaluation.executions for issue in item.observed_issue_codes
    )
    body = {
        "fixture_id": selected.fixture_id,
        "source_count": len(selected.sources),
        "operation_count": len(selected.operations),
        "case_count": len(selected.cases),
        "positive_count": len(selected.positive_cases),
        "control_count": len(selected.control_cases),
        "state_counts": dict(sorted(state_counts.items())),
        "family_counts": dict(sorted(family_counts.items())),
        "operation_counts": dict(sorted(operation_counts.items())),
        "scenario_counts": dict(sorted(scenario_counts.items())),
        "issue_counts": dict(sorted(issue_counts.items())),
        "check_count": len(evaluation.checks),
        "accepted": evaluation.accepted,
    }
    return body | {"content_address": addressed(body, "evidence-architecture-metrics")}


def evidence_architecture_metric_invariants(metrics: dict[str, Any]) -> tuple[str, ...]:
    failures: list[str] = []
    for name, required in (
        ("source_count", 19),
        ("operation_count", 16),
        ("case_count", 64),
        ("positive_count", 16),
        ("control_count", 48),
    ):
        if metrics.get(name) != required:
            failures.append(name)
    if any(value != 4 for value in metrics.get("operation_counts", {}).values()):
        failures.append("operation_balance")
    if metrics.get("family_counts") != {
        "evidence_lifecycle_frontier": 16,
        "lifecycle_beta_frontier": 32,
        "evidence_release_frontier": 16,
    }:
        failures.append("family_balance")
    if any(value != 16 for value in metrics.get("scenario_counts", {}).values()):
        failures.append("scenario_balance")
    return tuple(failures)


def evidence_architecture_metric_table(metrics: dict[str, Any]) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "metric": name,
            "value": metrics.get(name),
            "address": addressed(
                {"metric": name, "value": metrics.get(name)}, "evidence-architecture-metric"
            ),
        }
        for name in (
            "source_count",
            "operation_count",
            "case_count",
            "positive_count",
            "control_count",
            "check_count",
            "accepted",
        )
    )


__all__ = [
    "evidence_architecture_metric_invariants",
    "evidence_architecture_metric_table",
    "evidence_architecture_metrics",
]
