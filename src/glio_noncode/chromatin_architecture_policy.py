"""Decision policy for D07 acceptance, review, and publication boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_architecture_contracts import (
    ChromatinArchitectureEvaluation,
    ChromatinArchitectureOperation,
    ChromatinArchitectureState,
    addressed,
)
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class ChromatinArchitecturePolicyDecision:
    case_id: str
    operation_id: str
    observed_state: ChromatinArchitectureState
    decision: str
    retained: bool
    publishable: bool
    reason: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinArchitecturePolicyReport:
    fixture_id: str
    decisions: tuple[ChromatinArchitecturePolicyDecision, ...]
    accepted: bool
    content_address: str

    @property
    def accepted_count(self) -> int:
        return sum(item.decision == "accept" for item in self.decisions)

    @property
    def review_count(self) -> int:
        return sum(item.decision == "review" for item in self.decisions)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted_count": self.accepted_count,
            "review_count": self.review_count,
        }


def _reason(operation: ChromatinArchitectureOperation, accepted: bool) -> str:
    if accepted and operation is ChromatinArchitectureOperation.EVIDENCE_PUBLISH:
        return "exact-context evidence bundle reached the publication boundary"
    if accepted:
        return "receipt passed its declared state, issue, count, and address checks"
    return "control or unresolved family result remains review-held"


def score_chromatin_architecture_policy(
    evaluation: ChromatinArchitectureEvaluation,
) -> ChromatinArchitecturePolicyReport:
    decisions = tuple(
        ChromatinArchitecturePolicyDecision(
            case_id=receipt.case_id,
            operation_id=receipt.operation_id,
            observed_state=receipt.observed_state,
            decision="accept"
            if receipt.passed and receipt.expected_state is ChromatinArchitectureState.ACCEPTED
            else "review",
            retained=receipt.passed,
            publishable=receipt.passed
            and receipt.expected_result_state in {"accepted", "published", "supported"},
            reason=_reason(
                next(
                    execution.operation
                    for execution in evaluation.executions
                    if execution.case_id == receipt.case_id
                ),
                receipt.passed and receipt.expected_state is ChromatinArchitectureState.ACCEPTED,
            ),
            content_address=addressed(
                {
                    "case_id": receipt.case_id,
                    "operation_id": receipt.operation_id,
                    "decision": "accept"
                    if receipt.passed
                    and receipt.expected_state is ChromatinArchitectureState.ACCEPTED
                    else "review",
                    "retained": receipt.passed,
                },
                "chromatin-policy-decision",
            ),
        )
        for receipt in evaluation.receipts
    )
    checks = (
        len(decisions) == len(evaluation.receipts),
        sum(item.decision == "accept" for item in decisions) == evaluation.positive_count,
        sum(item.decision == "review" for item in decisions) == evaluation.control_count,
        all(item.publishable <= item.retained for item in decisions),
        all(item.content_address.startswith("sha256:") for item in decisions),
    )
    body = {"fixture_id": evaluation.fixture_id, "decisions": decisions, "checks": checks}
    return ChromatinArchitecturePolicyReport(
        evaluation.fixture_id,
        decisions,
        all(checks),
        addressed(body, "chromatin-policy"),
    )


__all__ = [
    "ChromatinArchitecturePolicyDecision",
    "ChromatinArchitecturePolicyReport",
    "score_chromatin_architecture_policy",
]
