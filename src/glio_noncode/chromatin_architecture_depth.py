"""Depth accounting for D07 implementation and evidence surfaces."""

from __future__ import annotations

from collections import Counter

from .chromatin_architecture_contracts import (
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
        "addressed_count": addressed_count,
        "family_counts": dict(family_counts),
        "plane_counts": dict(plane_counts),
        "check_count": len(evaluation.checks),
    }
    return ChromatinArchitectureDepthReport(
        **body, content_address=addressed(body, "chromatin-depth")
    )


__all__ = ["chromatin_architecture_depth_report"]
