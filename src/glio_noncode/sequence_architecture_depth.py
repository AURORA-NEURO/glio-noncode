"""Depth accounting for D06 sequence architecture."""

from __future__ import annotations

from .sequence_architecture_contracts import (
    SequenceArchitectureDepthReport,
    SequenceArchitectureEvaluation,
    SequenceArchitectureFixture,
    SequenceArchitectureLedger,
    SequenceArchitecturePlan,
    SequenceArchitectureReviewQueue,
    SequenceArchitectureRuntime,
    addressed,
)


def sequence_architecture_depth_report(
    fixture: SequenceArchitectureFixture,
    evaluation: SequenceArchitectureEvaluation,
    plan: SequenceArchitecturePlan,
    review_queue: SequenceArchitectureReviewQueue,
    ledger: SequenceArchitectureLedger,
    runtime: SequenceArchitectureRuntime,
) -> SequenceArchitectureDepthReport:
    addressed_count = (
        len(fixture.sources)
        + len(fixture.operations)
        + len(fixture.cases)
        + len(evaluation.receipts)
        + len(ledger.events)
    )
    accepted = (
        addressed_count == 17 + 16 + 64 + 64 + 64
        and len(runtime.stages) == 20
        and len(runtime.artifacts) == 6
    )
    body = {
        "fixture_id": fixture.fixture_id,
        "source_count": len(fixture.sources),
        "operation_count": len(fixture.operations),
        "case_count": len(fixture.cases),
        "receipt_count": len(evaluation.receipts),
        "ledger_count": len(ledger.events),
        "stage_count": len(runtime.stages),
        "artifact_count": len(runtime.artifacts),
        "addressed_count": addressed_count,
        "accepted": accepted,
    }
    return SequenceArchitectureDepthReport(
        **body, content_address=addressed(body, "sequence-depth")
    )


__all__ = ["sequence_architecture_depth_report"]
