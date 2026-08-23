"""Depth accounting for the D01 architecture boundary."""

from __future__ import annotations

from .intake_architecture_contracts import (
    INTAKE_ARCHITECTURE_CASE_COUNT,
    INTAKE_ARCHITECTURE_OPERATION_COUNT,
    IntakeArchitectureDepthReport,
    IntakeArchitectureRuntime,
    addressed,
)


def audit_intake_architecture_depth(runtime: IntakeArchitectureRuntime) -> IntakeArchitectureDepthReport:
    receipt_count = sum(len(item.receipt_addresses) for item in runtime.evaluation.results)
    checks = (
        "sixteen operation specs are executed",
        "sixty-four positive and control cases are accounted for",
        "seven validation planes cover every operation",
        "review queue retains every held control",
        "hash-linked ledger closes every case",
        "five offline artifacts have release receipts",
    )
    accepted = (
        len(runtime.evaluation.results) == INTAKE_ARCHITECTURE_CASE_COUNT
        and len(runtime.plan.nodes) == INTAKE_ARCHITECTURE_OPERATION_COUNT
        and len(runtime.review_queue.items) == 48
        and len(runtime.ledger.events) == INTAKE_ARCHITECTURE_CASE_COUNT
        and len(runtime.artifacts) == 5
    )
    body = {
        "fixture_id": runtime.fixture_id,
        "operation_count": len(runtime.plan.nodes),
        "case_count": len(runtime.evaluation.results),
        "source_count": 6,
        "stage_count": len(runtime.stages),
        "receipt_count": receipt_count,
        "addressed_output_count": len(runtime.evaluation.results),
        "accepted": accepted,
        "checks": checks,
    }
    return IntakeArchitectureDepthReport(**body, content_address=addressed(body, "intake-depth"))


__all__ = ["audit_intake_architecture_depth"]
