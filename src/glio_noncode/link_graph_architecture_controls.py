"""D10 control coverage accounting."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .link_graph_architecture_contracts import (
    LinkGraphArchitectureEvaluation,
    LinkGraphArchitectureFixture,
)


def link_graph_architecture_control_coverage(
    fixture: LinkGraphArchitectureFixture, evaluation: LinkGraphArchitectureEvaluation
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


def link_graph_architecture_controls_are_closed(
    fixture: LinkGraphArchitectureFixture, evaluation: LinkGraphArchitectureEvaluation
) -> bool:
    return bool(link_graph_architecture_control_coverage(fixture, evaluation)["balanced"])


__all__ = [
    "link_graph_architecture_control_coverage",
    "link_graph_architecture_controls_are_closed",
]
