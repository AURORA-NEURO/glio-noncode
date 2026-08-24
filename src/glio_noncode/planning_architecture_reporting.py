"""Human-readable and machine-readable D13 runtime reporting."""

from __future__ import annotations

import json
from typing import Any

from .planning_architecture_contract_matrix import planning_architecture_contract_matrix_summary
from .planning_architecture_contracts import (
    PlanningArchitectureEvaluation,
    PlanningArchitectureFixture,
    PlanningArchitectureRuntime,
    addressed,
)
from .planning_architecture_controls import planning_architecture_control_summary
from .planning_architecture_metrics import planning_architecture_metrics
from .planning_architecture_public_data import default_planning_architecture_fixture
from .planning_architecture_views import (
    planning_architecture_evaluation_view,
    planning_architecture_runtime_view,
)


def build_planning_architecture_report(
    fixture: PlanningArchitectureFixture | None = None,
    evaluation: PlanningArchitectureEvaluation | None = None,
    runtime: PlanningArchitectureRuntime | None = None,
) -> dict[str, Any]:
    selected = fixture or (
        runtime.fixture if runtime is not None else default_planning_architecture_fixture()
    )
    resolved_evaluation = evaluation or (runtime.evaluation if runtime is not None else None)
    if resolved_evaluation is None:
        from .planning_architecture_operations import evaluate_planning_architecture_fixture

        resolved_evaluation = evaluate_planning_architecture_fixture(selected)
    metrics = planning_architecture_metrics(selected, resolved_evaluation)
    body = {
        "module": "D13 planning architecture",
        "fixture_id": selected.fixture_id,
        "boundary": selected.boundary,
        "context_key": selected.context_key,
        "metrics": metrics,
        "evaluation": planning_architecture_evaluation_view(resolved_evaluation),
        "contract_matrix": planning_architecture_contract_matrix_summary(selected),
        "control_summary": planning_architecture_control_summary(selected),
        "runtime": planning_architecture_runtime_view(runtime) if runtime is not None else None,
        "limitations": [
            "public aggregate planning receipts only",
            "planning outputs are not efficacy, causality, or clinical decisions",
            "held states remain visible for external review",
        ],
    }
    return body | {"content_address": addressed(body, "planning-report")}


def planning_architecture_report_json(
    fixture: PlanningArchitectureFixture | None = None,
    evaluation: PlanningArchitectureEvaluation | None = None,
    runtime: PlanningArchitectureRuntime | None = None,
) -> str:
    return (
        json.dumps(
            build_planning_architecture_report(fixture, evaluation, runtime),
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def planning_architecture_report_markdown(
    report: dict[str, Any],
) -> str:
    metrics = report["metrics"]
    lines = [
        "# D13 Planning Architecture Report",
        "",
        f"- Fixture: `{report['fixture_id']}`",
        f"- Boundary: `{report['boundary']}`",
        f"- Sources: {metrics['source_count']}",
        f"- Operations: {metrics['operation_count']}",
        (
            f"- Cases: {metrics['case_count']} ({metrics['positive_count']} positive, "
            f"{metrics['control_count']} controls)"
        ),
        f"- Evaluation checks: {metrics['check_count']}",
        f"- Accepted: `{metrics['accepted']}`",
        "",
        "## State counts",
        "",
    ]
    lines.extend(f"- `{key}`: {value}" for key, value in sorted(metrics["state_counts"].items()))
    lines.extend(("", "## Boundary", "", *[f"- {item}" for item in report["limitations"]], ""))
    return "\n".join(lines)


__all__ = [
    "build_planning_architecture_report",
    "planning_architecture_report_json",
    "planning_architecture_report_markdown",
]
