"""D09 implementation depth accounting."""

from __future__ import annotations

from collections import Counter

from .topology_architecture_contracts import (
    TopologyArchitectureDepthReport,
    TopologyArchitectureEvaluation,
    TopologyArchitectureFixture,
    addressed,
)


def assess_topology_architecture_depth(
    fixture: TopologyArchitectureFixture, evaluation: TopologyArchitectureEvaluation | None = None
) -> TopologyArchitectureDepthReport:
    addresses = (
        [item.content_address for item in fixture.sources]
        + [item.content_address for item in fixture.operations]
        + [item.content_address for item in fixture.cases]
    )
    state_count = 0
    issue_code_count = 0
    if evaluation:
        addresses.extend(item.output_address for item in evaluation.executions)
        state_count = len({item.observed_result_state for item in evaluation.executions})
        issue_code_count = len(
            {issue for item in evaluation.executions for issue in item.issue_codes}
        )
    body = {
        "fixture_id": fixture.fixture_id,
        "operation_count": len(fixture.operations),
        "case_count": len(fixture.cases),
        "positive_count": len(fixture.positive_cases),
        "control_count": len(fixture.control_cases),
        "source_count": len(fixture.sources),
        "family_count": len({item.family for item in fixture.operations}),
        "addressed_count": sum(str(item).startswith("sha256:") for item in addresses),
        "family_counts": dict(
            sorted(Counter(item.family.value for item in fixture.operations).items())
        ),
        "plane_counts": dict(
            sorted(Counter(item.plane.value for item in fixture.operations).items())
        ),
        "check_count": len(evaluation.checks) if evaluation else 0,
        "state_count": state_count,
        "issue_code_count": issue_code_count,
    }
    return TopologyArchitectureDepthReport(
        **body, content_address=addressed(body, "topology-depth")
    )


def topology_architecture_depth_percent(report: TopologyArchitectureDepthReport) -> float:
    targets = (17, 16, 64, 4, 458)
    observed = (
        report.source_count,
        report.operation_count,
        report.case_count,
        report.family_count,
        report.check_count,
    )
    return round(
        100.0 * min(value / target for value, target in zip(observed, targets, strict=True)), 2
    )


__all__ = ["assess_topology_architecture_depth", "topology_architecture_depth_percent"]
