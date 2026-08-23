"""Depth accounting for the D08 implementation surface."""

from __future__ import annotations

from collections import Counter

from .cell_state_architecture_contracts import (
    CellStateArchitectureDepthReport,
    CellStateArchitectureEvaluation,
    CellStateArchitectureFixture,
    addressed,
)


def assess_cell_state_architecture_depth(
    fixture: CellStateArchitectureFixture, evaluation: CellStateArchitectureEvaluation | None = None
) -> CellStateArchitectureDepthReport:
    addresses = [item.content_address for item in fixture.sources]
    addresses.extend(item.content_address for item in fixture.operations)
    addresses.extend(item.content_address for item in fixture.cases)
    if evaluation:
        addresses.extend(item.output_address for item in evaluation.executions)
    body = {
        "fixture_id": fixture.fixture_id,
        "operation_count": len(fixture.operations),
        "case_count": len(fixture.cases),
        "positive_count": len(fixture.positive_cases),
        "control_count": len(fixture.control_cases),
        "source_count": len(fixture.sources),
        "addressed_count": sum(str(item).startswith("sha256:") for item in addresses),
        "family_counts": dict(
            sorted(Counter(item.family.value for item in fixture.operations).items())
        ),
        "plane_counts": dict(
            sorted(Counter(item.plane.value for item in fixture.operations).items())
        ),
        "check_count": len(evaluation.checks) if evaluation else 0,
    }
    return CellStateArchitectureDepthReport(
        **body, content_address=addressed(body, "cell-state-depth")
    )


def depth_percent(report: CellStateArchitectureDepthReport) -> float:
    """Report completion against the fixed D08 operation/case/address targets."""
    targets = (16, 64, 16 + 16 + 64, 392)
    observed = (
        report.operation_count,
        report.case_count,
        report.source_count + report.operation_count + report.case_count,
        report.check_count,
    )
    return round(
        100.0 * min((value / target for value, target in zip(observed, targets, strict=True))), 2
    )


__all__ = ["assess_cell_state_architecture_depth", "depth_percent"]
