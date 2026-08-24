"""Depth accounting for evidence architecture coverage and controls."""

from __future__ import annotations

from .evidence_architecture_contracts import (
    EvidenceArchitectureDepthReport,
    EvidenceArchitectureEvaluation,
    EvidenceArchitectureFixture,
    addressed,
)
from .evidence_architecture_public_data import default_evidence_architecture_fixture


def assess_evidence_architecture_depth(
    fixture: EvidenceArchitectureFixture | None = None,
    evaluation: EvidenceArchitectureEvaluation | None = None,
) -> EvidenceArchitectureDepthReport:
    selected = fixture or default_evidence_architecture_fixture()
    if evaluation is None:
        from .evidence_architecture_operations import evaluate_evidence_architecture_fixture

        evaluation = evaluate_evidence_architecture_fixture(selected)
    addresses = (
        {item.content_address for item in selected.sources}
        | {item.content_address for item in selected.operations}
        | {item.content_address for item in selected.cases}
        | {item.content_address for item in evaluation.checks}
        | {item.output_address for item in evaluation.executions}
    )
    states = {item.observed_state.value for item in evaluation.executions}
    issues = {issue for item in evaluation.executions for issue in item.observed_issue_codes}
    report = EvidenceArchitectureDepthReport(
        selected.fixture_id,
        len(selected.sources),
        len(selected.operations),
        len(selected.cases),
        len(selected.positive_cases),
        len(selected.control_cases),
        len(selected.family_set),
        len(evaluation.checks),
        len(addresses),
        len(states),
        len(issues),
        addressed(
            {
                "fixture_id": selected.fixture_id,
                "source_count": len(selected.sources),
                "operation_count": len(selected.operations),
                "case_count": len(selected.cases),
                "check_count": len(evaluation.checks),
                "addressed_count": len(addresses),
            },
            "evidence-architecture-depth",
        ),
    )
    return report


def evidence_architecture_depth_summary(
    report: EvidenceArchitectureDepthReport,
) -> dict[str, object]:
    return {
        "fixture_id": report.fixture_id,
        "source_count": report.source_count,
        "operation_count": report.operation_count,
        "case_count": report.case_count,
        "positive_count": report.positive_count,
        "control_count": report.control_count,
        "check_count": report.check_count,
        "addressed_count": report.addressed_count,
        "state_count": report.state_count,
        "issue_code_count": report.issue_code_count,
    }


__all__ = ["assess_evidence_architecture_depth", "evidence_architecture_depth_summary"]
