"""Claim-boundary checks for the lifecycle beta frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_contracts import LifecycleBetaFrontierEvaluation, LifecycleBetaFrontierState
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierClaimBoundaryCheck:
    check_id: str
    record_id: str | None
    passed: bool
    claim_class: str
    allowed: bool
    reason: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierClaimBoundaryReport:
    checks: tuple[LifecycleBetaFrontierClaimBoundaryCheck, ...]
    accepted: bool
    failed_check_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_lifecycle_beta_frontier_claim_boundary(evaluation: LifecycleBetaFrontierEvaluation) -> LifecycleBetaFrontierClaimBoundaryReport:
    checks = []
    for item in evaluation.executions:
        claim_class = "aggregate_review_record"
        allowed = item.state not in {LifecycleBetaFrontierState.APPROVED, LifecycleBetaFrontierState.SUPPORTED} or item.role.value == "positive"
        reason = "receipt is bounded to aggregate research review" if allowed else "unresolved evidence cannot be promoted"
        body = {"check_id": item.record_id, "record_id": item.record_id, "passed": allowed, "claim_class": claim_class, "allowed": allowed, "reason": reason}
        checks.append(LifecycleBetaFrontierClaimBoundaryCheck(**body, content_address=content_hash(body)))
    failed = tuple(item.check_id for item in checks if not item.passed)
    return LifecycleBetaFrontierClaimBoundaryReport(tuple(checks), not failed, failed, content_hash({"checks": tuple(checks), "failed": failed}))


__all__ = ["LifecycleBetaFrontierClaimBoundaryCheck", "LifecycleBetaFrontierClaimBoundaryReport", "evaluate_lifecycle_beta_frontier_claim_boundary"]
