"""D12 implementation depth accounting."""

from __future__ import annotations

from .cohort_architecture_contracts import (
    CohortArchitectureDepthReport,
    CohortArchitectureEvaluation,
    CohortArchitectureFixture,
    addressed,
)


def assess_cohort_architecture_depth(
    fixture: CohortArchitectureFixture,
    evaluation: CohortArchitectureEvaluation | None = None,
) -> CohortArchitectureDepthReport:
    addresses = (
        [item.content_address for item in fixture.sources]
        + [item.content_address for item in fixture.operations]
        + [item.content_address for item in fixture.cases]
    )
    if evaluation:
        addresses.extend(item.output_address for item in evaluation.executions)
    body = {
        "fixture_id": fixture.fixture_id,
        "source_count": len(fixture.sources),
        "operation_count": len(fixture.operations),
        "case_count": len(fixture.cases),
        "positive_count": len(fixture.positive_cases),
        "control_count": len(fixture.control_cases),
        "family_count": len({item.family for item in fixture.operations}),
        "check_count": len(evaluation.checks) if evaluation else 0,
        "addressed_count": sum(str(item).strip() != "" for item in addresses),
    }
    return CohortArchitectureDepthReport(
        **body,
        content_address=addressed(body, "cohort-depth"),
    )


def cohort_architecture_depth_percent(report: CohortArchitectureDepthReport) -> float:
    observed = (
        report.source_count,
        report.operation_count,
        report.case_count,
        report.family_count,
        report.check_count,
    )
    targets = (22, 16, 64, 4, 392)
    return round(
        100.0 * min(value / target for value, target in zip(observed, targets, strict=True)),
        2,
    )


__all__ = ["assess_cohort_architecture_depth", "cohort_architecture_depth_percent"]
