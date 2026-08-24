"""D12 scenario control coverage accounting."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .cohort_architecture_contracts import (
    CohortArchitectureEvaluation,
    CohortArchitectureFixture,
)


def cohort_architecture_control_coverage(
    fixture: CohortArchitectureFixture,
    evaluation: CohortArchitectureEvaluation,
) -> dict[str, Any]:
    expected = Counter(item.scenario.value for item in fixture.cases)
    observed = Counter(item.scenario.value for item in evaluation.executions)
    return {
        "rows": {
            scenario: {"expected": expected[scenario], "observed": observed[scenario]}
            for scenario in ("control_a", "control_b", "control_c")
        },
        "positive_paths": expected["positive"],
        "held_paths": sum(expected[item] for item in ("control_a", "control_b", "control_c")),
        "balanced": expected == observed
        and all(
            expected[item] == 16 for item in ("positive", "control_a", "control_b", "control_c")
        ),
    }


def cohort_architecture_controls_are_closed(
    fixture: CohortArchitectureFixture,
    evaluation: CohortArchitectureEvaluation,
) -> bool:
    return bool(cohort_architecture_control_coverage(fixture, evaluation)["balanced"])


__all__ = ["cohort_architecture_control_coverage", "cohort_architecture_controls_are_closed"]
