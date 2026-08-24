"""D11 implementation depth accounting."""

from __future__ import annotations

from .causal_architecture_contracts import (
    CausalArchitectureDepthReport,
    CausalArchitectureEvaluation,
    CausalArchitectureFixture,
    addressed,
)


def assess_causal_architecture_depth(
    fixture: CausalArchitectureFixture, evaluation: CausalArchitectureEvaluation | None = None
) -> CausalArchitectureDepthReport:
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
        "check_count": len(evaluation.checks) if evaluation else 0,
        "addressed_count": sum(str(item).startswith("sha256:") for item in addresses),
    }
    return CausalArchitectureDepthReport(**body, content_address=addressed(body, "causal-depth"))


def causal_architecture_depth_percent(report: CausalArchitectureDepthReport) -> float:
    observed = (report.source_count, report.operation_count, report.case_count, report.check_count)
    targets = (20, 16, 64, 392)
    return round(
        100.0 * min(value / target for value, target in zip(observed, targets, strict=True)), 2
    )


__all__ = ["assess_causal_architecture_depth", "causal_architecture_depth_percent"]
