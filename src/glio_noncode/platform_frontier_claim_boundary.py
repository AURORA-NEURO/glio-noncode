"""Claim and output boundary checks for platform receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_contracts import PlatformFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierClaimBoundaryCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierClaimBoundaryReport:
    checks: tuple[PlatformFrontierClaimBoundaryCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_platform_frontier_claim_boundary(evaluation: PlatformFrontierEvaluation) -> PlatformFrontierClaimBoundaryReport:
    serialized = str(evaluation.to_dict()).lower()
    values = (
        ("no-clinical-claim", "clinical" not in serialized, "clinical terminology is absent from runtime outputs"),
        ("no-treatment-claim", "treatment" not in serialized, "treatment terminology is absent from runtime outputs"),
        ("control-visible", all(not item.accepted for item in evaluation.executions if item.role.value == "control"), "control rows remain non-positive"),
        ("positive-bounded", sum(item.accepted for item in evaluation.executions) == 4, "only four positive paths are accepted"),
    )
    checks = []
    for check_id, passed, detail in values:
        body = {"check_id": check_id, "passed": passed, "detail": detail}
        checks.append(PlatformFrontierClaimBoundaryCheck(**body, content_address=content_hash(body)))
    return PlatformFrontierClaimBoundaryReport(tuple(checks), all(item.passed for item in checks), content_hash(tuple(checks)))


__all__ = ["PlatformFrontierClaimBoundaryCheck", "PlatformFrontierClaimBoundaryReport", "evaluate_platform_frontier_claim_boundary"]
