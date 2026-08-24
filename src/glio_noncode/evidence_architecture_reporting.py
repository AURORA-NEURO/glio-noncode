"""Human-readable and machine-readable D14 runtime reporting."""

from __future__ import annotations

import json
from typing import Any

from .evidence_architecture_contract_matrix import evidence_architecture_contract_matrix_summary
from .evidence_architecture_contracts import (
    EvidenceArchitectureEvaluation,
    EvidenceArchitectureFixture,
    EvidenceArchitectureRuntime,
    addressed,
)
from .evidence_architecture_controls import evidence_architecture_control_summary
from .evidence_architecture_metrics import evidence_architecture_metrics
from .evidence_architecture_public_data import default_evidence_architecture_fixture
from .evidence_architecture_views import (
    evidence_architecture_evaluation_view,
    evidence_architecture_runtime_view,
)


def build_evidence_architecture_report(
    fixture: EvidenceArchitectureFixture | None = None,
    evaluation: EvidenceArchitectureEvaluation | None = None,
    runtime: EvidenceArchitectureRuntime | None = None,
) -> dict[str, Any]:
    selected = fixture or (
        runtime.fixture if runtime is not None else default_evidence_architecture_fixture()
    )
    resolved = evaluation or (runtime.evaluation if runtime is not None else None)
    if resolved is None:
        from .evidence_architecture_operations import evaluate_evidence_architecture_fixture

        resolved = evaluate_evidence_architecture_fixture(selected)
    metrics = evidence_architecture_metrics(selected, resolved)
    body = {
        "module": "D14 evidence architecture",
        "fixture_id": selected.fixture_id,
        "boundary": selected.boundary,
        "context_key": selected.context_key,
        "metrics": metrics,
        "evaluation": evidence_architecture_evaluation_view(resolved),
        "contract_matrix": evidence_architecture_contract_matrix_summary(selected),
        "control_summary": evidence_architecture_control_summary(selected),
        "runtime": evidence_architecture_runtime_view(runtime) if runtime is not None else None,
        "limitations": [
            "public aggregate lifecycle receipts only",
            "evidence outputs are not efficacy, causality, or clinical decisions",
            "held states remain visible for external review",
        ],
    }
    return body | {"content_address": addressed(body, "evidence-architecture-report")}


def evidence_architecture_report_json(
    fixture: EvidenceArchitectureFixture | None = None,
    evaluation: EvidenceArchitectureEvaluation | None = None,
    runtime: EvidenceArchitectureRuntime | None = None,
) -> str:
    return (
        json.dumps(
            build_evidence_architecture_report(fixture, evaluation, runtime),
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def evidence_architecture_report_markdown(report: dict[str, Any]) -> str:
    metrics = report["metrics"]
    lines = [
        "# D14 Evidence Architecture Report",
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
    "build_evidence_architecture_report",
    "evidence_architecture_report_json",
    "evidence_architecture_report_markdown",
]
