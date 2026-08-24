"""Depth accounting for D07 implementation and evidence surfaces."""

from __future__ import annotations

from collections import Counter

from .chromatin_architecture_contracts import (
    CHROMATIN_ARCHITECTURE_CASE_COUNT,
    CHROMATIN_ARCHITECTURE_FAMILY_COUNT,
    CHROMATIN_ARCHITECTURE_OPERATION_COUNT,
    CHROMATIN_ARCHITECTURE_SOURCE_COUNT,
    ChromatinArchitectureDepthReport,
    ChromatinArchitectureEvaluation,
    ChromatinArchitectureFixture,
    addressed,
)


def chromatin_architecture_depth_report(
    fixture: ChromatinArchitectureFixture,
    evaluation: ChromatinArchitectureEvaluation,
) -> ChromatinArchitectureDepthReport:
    family_counts = Counter(item.family.value for item in fixture.operations)
    plane_counts = Counter(item.plane.value for item in fixture.operations)
    addressed_count = (
        len(fixture.sources)
        + len(fixture.operations)
        + len(fixture.cases)
        + len(evaluation.executions)
        + len(evaluation.receipts)
        + len(evaluation.checks)
    )
    body = {
        "fixture_id": fixture.fixture_id,
        "operation_count": len(fixture.operations),
        "case_count": len(fixture.cases),
        "positive_count": len(fixture.positive_cases),
        "control_count": len(fixture.control_cases),
        "source_count": len(fixture.sources),
        "family_count": len(family_counts),
        "addressed_count": addressed_count,
        "family_counts": dict(family_counts),
        "plane_counts": dict(plane_counts),
        "check_count": len(evaluation.checks),
        "state_count": len({item.observed_result_state for item in evaluation.executions}),
        "issue_code_count": len(
            {issue for item in evaluation.executions for issue in item.issue_codes}
        ),
    }
    return ChromatinArchitectureDepthReport(
        **body, content_address=addressed(body, "chromatin-depth")
    )


def chromatin_architecture_depth_percent(report: ChromatinArchitectureDepthReport) -> float:
    """Report completion against the fixed D07 source/operation/case/check targets."""
    targets = (
        CHROMATIN_ARCHITECTURE_SOURCE_COUNT,
        CHROMATIN_ARCHITECTURE_OPERATION_COUNT,
        CHROMATIN_ARCHITECTURE_CASE_COUNT,
        CHROMATIN_ARCHITECTURE_FAMILY_COUNT,
        458,
    )
    observed = (
        report.source_count,
        report.operation_count,
        report.case_count,
        report.family_count,
        report.check_count,
    )
    return round(
        100.0 * min(value / target for value, target in zip(observed, targets, strict=True)),
        2,
    )


__all__ = ["chromatin_architecture_depth_percent", "chromatin_architecture_depth_report"]
