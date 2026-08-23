"""Control coverage and failure routing for D09."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .topology_architecture_contracts import (
    TopologyArchitectureEvaluation,
    TopologyArchitectureFixture,
)


def topology_architecture_control_coverage(
    fixture: TopologyArchitectureFixture, evaluation: TopologyArchitectureEvaluation
) -> dict[str, Any]:
    expected = Counter(item.scenario.value for item in fixture.cases)
    observed = Counter(item.scenario.value for item in evaluation.executions)
    issues = Counter(code for item in evaluation.executions for code in item.issue_codes)
    rows = {
        scenario: {
            "expected": expected[scenario],
            "observed": observed[scenario],
            "issue_code": code,
        }
        for scenario, code in (
            ("foreign_context", "context_mismatch"),
            ("malformed_input", "malformed_input"),
            ("identity_conflict", "identity_conflict"),
        )
    }
    return {
        "rows": rows,
        "positive_paths": expected["positive"],
        "held_paths": sum(item["observed"] for item in rows.values()),
        "issue_code_counts": dict(sorted(issues.items())),
        "balanced": all(item["expected"] == item["observed"] == 16 for item in rows.values()),
    }


def topology_architecture_controls_are_closed(
    fixture: TopologyArchitectureFixture, evaluation: TopologyArchitectureEvaluation
) -> bool:
    return topology_architecture_control_coverage(fixture, evaluation)["balanced"]


__all__ = ["topology_architecture_control_coverage", "topology_architecture_controls_are_closed"]
