"""Human-readable and machine-readable D16 runtime reporting."""

from __future__ import annotations

import json
from typing import Any

from .platform_execution_architecture_contracts import (
    PlatformExecutionEvaluation,
    PlatformExecutionFixture,
    PlatformExecutionRuntime,
    addressed,
)
from .platform_execution_architecture_matrix import platform_execution_contract_matrix
from .platform_execution_architecture_metrics import platform_execution_metrics
from .platform_execution_architecture_public_data import default_platform_execution_fixture


def build_platform_execution_report(
    fixture: PlatformExecutionFixture | None = None,
    evaluation: PlatformExecutionEvaluation | None = None,
    runtime: PlatformExecutionRuntime | None = None,
) -> dict[str, Any]:
    selected = fixture or (
        runtime.fixture if runtime is not None else default_platform_execution_fixture()
    )
    resolved = evaluation or (runtime.evaluation if runtime is not None else None)
    if resolved is None:
        from .platform_execution_architecture_operations import evaluate_platform_execution_fixture

        resolved = evaluate_platform_execution_fixture(selected)
    metrics = platform_execution_metrics(selected, resolved)
    body = {
        "module": "D16 platform execution architecture",
        "fixture_id": selected.fixture_id,
        "boundary": selected.boundary,
        "context_key": selected.context_key,
        "metrics": metrics,
        "operations": platform_execution_contract_matrix(selected),
        "evaluation": resolved.to_dict(),
        "runtime": runtime.to_dict() if runtime is not None else None,
        "limitations": [
            "public aggregate execution receipts only",
            "workspace outputs are not efficacy, causal, or clinical decisions",
            "held, denied, and out-of-domain states remain visible for review",
            "deployment controls require local policy, network, and release validation",
        ],
    }
    return body | {"content_address": addressed(body, "platform-execution-report")}


def platform_execution_report_json(
    fixture: PlatformExecutionFixture | None = None,
    evaluation: PlatformExecutionEvaluation | None = None,
    runtime: PlatformExecutionRuntime | None = None,
) -> str:
    return (
        json.dumps(
            build_platform_execution_report(fixture, evaluation, runtime), indent=2, sort_keys=True
        )
        + "\n"
    )


def platform_execution_report_markdown(report: dict[str, Any]) -> str:
    metrics = report["metrics"]
    lines = [
        "# D16 Platform Execution Architecture Report",
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
    lines.extend(("", "## Issue controls", ""))
    lines.extend(f"- `{key}`: {value}" for key, value in sorted(metrics["issue_counts"].items()))
    lines.extend(("", "## Boundary", "", *[f"- {item}" for item in report["limitations"]], ""))
    return "\n".join(lines)


__all__ = [
    "build_platform_execution_report",
    "platform_execution_report_json",
    "platform_execution_report_markdown",
]
