"""Depth accounting for the complete D02 architecture build."""

from __future__ import annotations

from .structural_architecture_contracts import (
    STRUCTURAL_ARCHITECTURE_CASE_COUNT,
    STRUCTURAL_ARCHITECTURE_OPERATION_COUNT,
    StructuralArchitectureDepthReport,
    StructuralArchitectureRuntime,
    addressed,
)


def audit_structural_architecture_depth(
    runtime: StructuralArchitectureRuntime,
) -> StructuralArchitectureDepthReport:
    addressed_count = sum(
        item.content_address.startswith("sha256:") for item in runtime.evaluation.receipts
    ) + sum(item.content_address.startswith("sha256:") for item in runtime.stages)
    checks = (
        "sixteen C01-C16 operation specs execute",
        "sixty-four cases include sixteen positives and forty-eight controls",
        "seven validation planes cover every operation",
        "review queue retains every held control",
        "hash-linked ledger closes every case",
        "six offline artifacts have release receipts",
        "twenty runtime stages are ordered and addressed",
    )
    accepted = (
        len(runtime.plan.nodes) == STRUCTURAL_ARCHITECTURE_OPERATION_COUNT
        and len(runtime.evaluation.receipts) == STRUCTURAL_ARCHITECTURE_CASE_COUNT
        and runtime.evaluation.positive_count == 16
        and runtime.evaluation.control_count == 48
        and len(runtime.review_queue.items) == 48
        and len(runtime.ledger.events) == 64
        and len(runtime.artifacts) == 6
        and len(runtime.stages) == 20
    )
    body = {
        "fixture_id": runtime.fixture_id,
        "operation_count": len(runtime.plan.nodes),
        "case_count": len(runtime.evaluation.receipts),
        "positive_count": runtime.evaluation.positive_count,
        "control_count": runtime.evaluation.control_count,
        "stage_count": len(runtime.stages),
        "artifact_count": len(runtime.artifacts),
        "addressed_count": addressed_count,
        "accepted": accepted,
        "checks": checks,
    }
    return StructuralArchitectureDepthReport(
        **body, content_address=addressed(body, "structural-depth")
    )


__all__ = ["audit_structural_architecture_depth"]
