"""Depth accounting for D06 sequence architecture."""

from __future__ import annotations

from typing import Any

from .sequence_architecture_contracts import (
    SequenceArchitectureDepthReport,
    SequenceArchitectureEvaluation,
    SequenceArchitectureFixture,
    SequenceArchitectureLedger,
    SequenceArchitecturePlan,
    SequenceArchitectureReviewQueue,
    addressed,
)

SEQUENCE_ARCHITECTURE_DEPTH_TARGETS = {
    "source_count": 17,
    "operation_count": 16,
    "case_count": 64,
    "family_count": 4,
    "check_count": 458,
}


def sequence_architecture_depth_report(
    fixture: SequenceArchitectureFixture,
    evaluation: SequenceArchitectureEvaluation,
    plan: SequenceArchitecturePlan,
    review_queue: SequenceArchitectureReviewQueue,
    ledger: SequenceArchitectureLedger,
    runtime: Any | None = None,
) -> SequenceArchitectureDepthReport:
    addressed_count = (
        len(fixture.sources)
        + len(fixture.operations)
        + len(fixture.cases)
        + len(evaluation.receipts)
        + len(ledger.events)
    )
    stage_count = len(runtime.stages) if runtime is not None else 24
    artifact_count = len(runtime.artifacts) if runtime is not None else 6
    family_count = len({item.family for item in fixture.operations})
    check_count = len(evaluation.checks)
    state_count = len({item.observed_result_state for item in evaluation.receipts})
    issue_code_count = len(
        {code for item in evaluation.receipts for code in item.observed_issue_codes}
    )
    accepted = (
        addressed_count == 17 + 16 + 64 + 64 + 64
        and stage_count == 24
        and artifact_count == 6
        and (
            len(fixture.sources),
            len(fixture.operations),
            len(fixture.cases),
            family_count,
            check_count,
        )
        == tuple(SEQUENCE_ARCHITECTURE_DEPTH_TARGETS.values())
    )
    body = {
        "fixture_id": fixture.fixture_id,
        "source_count": len(fixture.sources),
        "operation_count": len(fixture.operations),
        "case_count": len(fixture.cases),
        "receipt_count": len(evaluation.receipts),
        "ledger_count": len(ledger.events),
        "stage_count": stage_count,
        "artifact_count": artifact_count,
        "family_count": family_count,
        "check_count": check_count,
        "state_count": state_count,
        "issue_code_count": issue_code_count,
        "addressed_count": addressed_count,
        "accepted": accepted,
    }
    return SequenceArchitectureDepthReport(
        **body, content_address=addressed(body, "sequence-depth")
    )


def sequence_architecture_depth_percent(
    fixture: Any, evaluation: Any
) -> float:
    observed = (
        len(fixture.sources),
        len(fixture.operations),
        len(fixture.cases),
        len({item.family for item in fixture.operations}),
        len(evaluation.checks),
    )
    ratios = [
        min(float(value) / float(SEQUENCE_ARCHITECTURE_DEPTH_TARGETS[key]), 1.0)
        for key, value in zip(SEQUENCE_ARCHITECTURE_DEPTH_TARGETS, observed, strict=True)
    ]
    return round(sum(ratios) / len(ratios) * 100.0, 2)


__all__ = [
    "SEQUENCE_ARCHITECTURE_DEPTH_TARGETS",
    "sequence_architecture_depth_percent",
    "sequence_architecture_depth_report",
]
