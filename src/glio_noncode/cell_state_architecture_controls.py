"""Control coverage accounting for exact-context D08 execution."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .cell_state_architecture_contracts import (
    CellStateArchitectureEvaluation,
    CellStateArchitectureFixture,
)


def cell_state_architecture_control_coverage(
    fixture: CellStateArchitectureFixture, evaluation: CellStateArchitectureEvaluation
) -> dict[str, Any]:
    expected = Counter(case.scenario.value for case in fixture.cases)
    observed = Counter(execution.scenario.value for execution in evaluation.executions)
    issue_codes = Counter(
        code for execution in evaluation.executions for code in execution.issue_codes
    )
    rows = {
        "foreign_context": {
            "expected": expected["foreign_context"],
            "observed": observed["foreign_context"],
            "issue_code": "context_mismatch",
        },
        "malformed_input": {
            "expected": expected["malformed_input"],
            "observed": observed["malformed_input"],
            "issue_code": "malformed_input",
        },
        "identity_conflict": {
            "expected": expected["identity_conflict"],
            "observed": observed["identity_conflict"],
            "issue_code": "identity_conflict",
        },
    }
    return {
        "rows": rows,
        "positive_paths": expected["positive"],
        "held_paths": sum(rows[item]["observed"] for item in rows),
        "issue_code_counts": dict(sorted(issue_codes.items())),
        "balanced": all(item["expected"] == item["observed"] == 16 for item in rows.values()),
    }


def control_coverage_is_closed(
    fixture: CellStateArchitectureFixture, evaluation: CellStateArchitectureEvaluation
) -> bool:
    return cell_state_architecture_control_coverage(fixture, evaluation)["balanced"]


__all__ = ["cell_state_architecture_control_coverage", "control_coverage_is_closed"]
