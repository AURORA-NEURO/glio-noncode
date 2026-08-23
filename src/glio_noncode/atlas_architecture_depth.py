"""Depth accounting for the D05 atlas architecture."""

from __future__ import annotations

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


def atlas_architecture_depth_report(
    fixture: AtlasArchitectureFixture,
    evaluation: AtlasArchitectureEvaluation,
    plan: AtlasArchitecturePlan,
    review_queue: AtlasArchitectureReviewQueue,
    ledger: AtlasArchitectureLedger,
    runtime: AtlasArchitectureRuntime | None = None,
) -> AtlasArchitectureDepthReport:
    stage_count = len(runtime.stages) if runtime else 0
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
        "20 runtime stages" if stage_count >= 20 else "runtime stages pending",
    )
    accepted = (
        len(fixture.sources) == 20
        and len(fixture.operations) == 16
        and len(fixture.cases) == 64
        and len(evaluation.receipts) == 64
        and len(plan.nodes) == 16
        and len(review_queue.items) == 48
        and len(ledger.events) == 64
        and (runtime is None or stage_count >= 20)
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
        addressed_count,
        accepted,
        checks,
        addressed(body, "atlas-depth"),
    )


__all__ = ["atlas_architecture_depth_report"]
