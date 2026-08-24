"""Human-readable and machine-readable D15 runtime reporting."""

from __future__ import annotations

import json
from typing import Any

from .workbench_architecture_contract_matrix import workbench_architecture_contract_matrix_summary
from .workbench_architecture_contracts import (
    WorkbenchArchitectureEvaluation,
    WorkbenchArchitectureFixture,
    WorkbenchArchitectureRuntime,
    addressed,
)
from .workbench_architecture_controls import workbench_architecture_control_summary
from .workbench_architecture_metrics import workbench_architecture_metrics
from .workbench_architecture_public_data import default_workbench_architecture_fixture
from .workbench_architecture_views import (
    workbench_architecture_evaluation_view,
    workbench_architecture_runtime_view,
)


def build_workbench_architecture_report(
    fixture: WorkbenchArchitectureFixture | None = None,
    evaluation: WorkbenchArchitectureEvaluation | None = None,
    runtime: WorkbenchArchitectureRuntime | None = None,
) -> dict[str, Any]:
    selected = fixture or (
        runtime.fixture if runtime is not None else default_workbench_architecture_fixture()
    )
    resolved = evaluation or (runtime.evaluation if runtime is not None else None)
    if resolved is None:
        from .workbench_architecture_operations import evaluate_workbench_architecture_fixture

        resolved = evaluate_workbench_architecture_fixture(selected)
    body = {
        "module": "D15 workbench architecture",
        "fixture_id": selected.fixture_id,
        "boundary": selected.boundary,
        "context_key": selected.context_key,
        "metrics": workbench_architecture_metrics(selected, resolved),
        "evaluation": workbench_architecture_evaluation_view(resolved),
        "contract_matrix": workbench_architecture_contract_matrix_summary(selected),
        "control_summary": workbench_architecture_control_summary(selected),
        "runtime": workbench_architecture_runtime_view(runtime) if runtime is not None else None,
        "limitations": [
            "public aggregate workbench receipts only",
            "workspace outputs are not efficacy, causal, or clinical decisions",
            "held states remain visible for external review",
        ],
    }
    return body | {"content_address": addressed(body, "workbench-architecture-report")}


def workbench_architecture_report_json(
    fixture: WorkbenchArchitectureFixture | None = None,
    evaluation: WorkbenchArchitectureEvaluation | None = None,
    runtime: WorkbenchArchitectureRuntime | None = None,
) -> str:
    return (
        json.dumps(
            build_workbench_architecture_report(fixture, evaluation, runtime),
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def workbench_architecture_report_markdown(report: dict[str, Any]) -> str:
    metrics = report["metrics"]
    lines = [
        "# D15 Workbench Architecture Report",
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
    "build_workbench_architecture_report",
    "workbench_architecture_report_json",
    "workbench_architecture_report_markdown",
]
