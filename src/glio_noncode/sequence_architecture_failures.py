"""Failure classification for D06 evaluation receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sequence_architecture_contracts import SequenceArchitectureEvaluation, addressed
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class SequenceArchitectureFailure:
    case_id: str
    operation_id: str
    category: str
    detail: str
    content_address: str


@dataclass(frozen=True, slots=True)
class SequenceArchitectureFailureReport:
    fixture_id: str
    failures: tuple[SequenceArchitectureFailure, ...]
    release_blocked: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def classify_sequence_architecture_failures(
    evaluation: SequenceArchitectureEvaluation,
) -> SequenceArchitectureFailureReport:
    failures = tuple(_failure(item) for item in evaluation.receipts if not item.passed)
    body = {
        "fixture_id": evaluation.fixture_id,
        "failures": failures,
        "release_blocked": bool(failures),
    }
    return SequenceArchitectureFailureReport(
        fixture_id=evaluation.fixture_id,
        failures=failures,
        release_blocked=bool(failures),
        content_address=addressed(body, "sequence-failure-report"),
    )


def _failure(receipt: Any) -> SequenceArchitectureFailure:
    if receipt.expected_state != receipt.observed_state:
        category, detail = "state_mismatch", "aggregate state differs from expected control policy"
    elif receipt.expected_issue_codes != receipt.observed_issue_codes:
        category, detail = "issue_mismatch", "family issue receipt differs from expected evidence"
    elif receipt.expected_counts != receipt.observed_counts:
        category, detail = "count_mismatch", "bounded counts differ"
    else:
        category, detail = "result_mismatch", "family result differs from operation expectation"
    body = {
        "case_id": receipt.case_id,
        "operation_id": receipt.operation_id,
        "category": category,
        "detail": detail,
    }
    return SequenceArchitectureFailure(**body, content_address=addressed(body, "sequence-failure"))


__all__ = [
    "SequenceArchitectureFailure",
    "SequenceArchitectureFailureReport",
    "classify_sequence_architecture_failures",
]
