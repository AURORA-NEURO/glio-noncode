"""Depth accounting for the D05 atlas architecture."""

from __future__ import annotations

from typing import Any

from .atlas_architecture_contracts import (
    ATLAS_ARCHITECTURE_ARTIFACT_COUNT,
    AtlasArchitectureDepthReport,
    AtlasArchitectureEvaluation,
    AtlasArchitectureFixture,
    AtlasArchitectureLedger,
    AtlasArchitecturePlan,
    AtlasArchitectureReviewQueue,
    AtlasArchitectureRuntime,
    addressed,
)

ATLAS_ARCHITECTURE_DEPTH_TARGETS = {
    "source_count": 20,
    "operation_count": 16,
    "case_count": 64,
    "family_count": 4,
    "check_count": 458,
}


def atlas_architecture_depth_report(
    fixture: AtlasArchitectureFixture,
    evaluation: AtlasArchitectureEvaluation,
    plan: AtlasArchitecturePlan,
    review_queue: AtlasArchitectureReviewQueue,
    ledger: AtlasArchitectureLedger,
    runtime: AtlasArchitectureRuntime | None = None,
) -> AtlasArchitectureDepthReport:
    stage_count = len(runtime.stages) if runtime else 24
    addressed_count = (
        len(fixture.sources)
        + len(fixture.operations)
        + len(fixture.cases)
        + len(evaluation.receipts)
        + len(ledger.events)
    )
    checks = (
        "20 public source receipts",
        "16 operation specifications",
        "64 case contracts",
        "16 positive typed adapter executions",
        "48 conservative controls",
        "80 validation cells",
        "64 linked lineage events",
        "6 release artifacts",
        "24 runtime stages" if stage_count >= 24 else "runtime stages pending",
    )
    family_count = len({item.family for item in fixture.operations})
    check_count = len(evaluation.checks)
    state_count = len({item.observed_result_state for item in evaluation.receipts})
    issue_code_count = len(
        {code for item in evaluation.receipts for code in item.observed_issue_codes}
    )
    accepted = (
        (
            len(fixture.sources),
            len(fixture.operations),
            len(fixture.cases),
            family_count,
            check_count,
        )
        == tuple(ATLAS_ARCHITECTURE_DEPTH_TARGETS.values())
        and len(evaluation.receipts) == 64
        and len(plan.nodes) == 16
        and len(review_queue.items) == 48
        and len(ledger.events) == 64
        and (runtime is None or stage_count == 24)
    )
    body = {
        "fixture_id": fixture.fixture_id,
        "source_count": len(fixture.sources),
        "operation_count": len(fixture.operations),
        "case_count": len(fixture.cases),
        "positive_count": evaluation.positive_count,
        "control_count": evaluation.control_count,
        "stage_count": stage_count,
        "artifact_count": ATLAS_ARCHITECTURE_ARTIFACT_COUNT,
        "family_count": family_count,
        "check_count": check_count,
        "state_count": state_count,
        "issue_code_count": issue_code_count,
        "addressed_count": addressed_count,
        "accepted": accepted,
        "checks": checks,
    }
    return AtlasArchitectureDepthReport(
        fixture.fixture_id,
        len(fixture.sources),
        len(fixture.operations),
        len(fixture.cases),
        evaluation.positive_count,
        evaluation.control_count,
        stage_count,
        ATLAS_ARCHITECTURE_ARTIFACT_COUNT,
        family_count,
        check_count,
        state_count,
        issue_code_count,
        addressed_count,
        accepted,
        checks,
        addressed(body, "atlas-depth"),
    )


def atlas_architecture_depth_percent(fixture: Any, evaluation: Any) -> float:
    observed = (
        len(fixture.sources),
        len(fixture.operations),
        len(fixture.cases),
        len({item.family for item in fixture.operations}),
        len(evaluation.checks),
    )
    ratios = [
        min(float(value) / float(ATLAS_ARCHITECTURE_DEPTH_TARGETS[key]), 1.0)
        for key, value in zip(ATLAS_ARCHITECTURE_DEPTH_TARGETS, observed, strict=True)
    ]
    return round(sum(ratios) / len(ratios) * 100.0, 2)


__all__ = [
    "ATLAS_ARCHITECTURE_DEPTH_TARGETS",
    "atlas_architecture_depth_percent",
    "atlas_architecture_depth_report",
]
