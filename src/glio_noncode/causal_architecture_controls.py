"""D11 positive and control coverage accounting."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .causal_architecture_contracts import CausalArchitectureEvaluation, CausalArchitectureFixture


def causal_architecture_control_coverage(
    fixture: CausalArchitectureFixture, evaluation: CausalArchitectureEvaluation
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


def causal_architecture_controls_are_closed(
    fixture: CausalArchitectureFixture, evaluation: CausalArchitectureEvaluation
) -> bool:
    return bool(causal_architecture_control_coverage(fixture, evaluation)["balanced"])


__all__ = ["causal_architecture_control_coverage", "causal_architecture_controls_are_closed"]
