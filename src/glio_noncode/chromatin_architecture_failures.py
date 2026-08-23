"""Closed failure vocabulary and classification for D07 receipts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .chromatin_architecture_contracts import ChromatinArchitectureEvaluation, addressed
from .serialization import jsonable


class ChromatinArchitectureFailureClass(StrEnum):
    CONTEXT = "context"
    INPUT = "input"
    IDENTITY = "identity"
    FAMILY = "family"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureFailure:
    case_id: str
    class_name: ChromatinArchitectureFailureClass
    issue_codes: tuple[str, ...]
    blocking: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureFailureReport:
    fixture_id: str
    failures: tuple[ChromatinArchitectureFailure, ...]
    class_counts: dict[str, int]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def classify_chromatin_architecture_failures(
    evaluation: ChromatinArchitectureEvaluation,
) -> ChromatinArchitectureFailureReport:
    failures: list[ChromatinArchitectureFailure] = []
    for receipt in evaluation.receipts:
        if receipt.expected_state.value == "accepted":
            class_name, blocking, detail = (
                ChromatinArchitectureFailureClass.NONE,
                False,
                "receipt passed",
            )
        elif "context_mismatch" in receipt.observed_issue_codes:
            class_name, blocking, detail = (
                ChromatinArchitectureFailureClass.CONTEXT,
                False,
                "foreign context remains outside the aggregate",
            )
        elif "malformed_input" in receipt.observed_issue_codes:
            class_name, blocking, detail = (
                ChromatinArchitectureFailureClass.INPUT,
                True,
                "input repair is required before delegation",
            )
        elif "identity_conflict" in receipt.observed_issue_codes:
            class_name, blocking, detail = (
                ChromatinArchitectureFailureClass.IDENTITY,
                True,
                "identity reconciliation is required",
            )
        else:
            class_name, blocking, detail = (
                ChromatinArchitectureFailureClass.FAMILY,
                True,
                "family result did not satisfy the aggregate contract",
            )
        body = {
            "case_id": receipt.case_id,
            "class_name": class_name,
            "issue_codes": receipt.observed_issue_codes,
            "blocking": blocking,
        }
        failures.append(
            ChromatinArchitectureFailure(
                receipt.case_id,
                class_name,
                receipt.observed_issue_codes,
                blocking,
                detail,
                addressed(body, "chromatin-failure"),
            )
        )
    counts: dict[str, int] = {}
    for item in failures:
        counts[item.class_name.value] = counts.get(item.class_name.value, 0) + 1
    body = {"fixture_id": evaluation.fixture_id, "failures": failures, "class_counts": counts}
    accepted = all(
        item.class_name
        in {
            ChromatinArchitectureFailureClass.NONE,
            ChromatinArchitectureFailureClass.CONTEXT,
            ChromatinArchitectureFailureClass.INPUT,
            ChromatinArchitectureFailureClass.IDENTITY,
        }
        for item in failures
    )
    return ChromatinArchitectureFailureReport(
        evaluation.fixture_id,
        tuple(failures),
        counts,
        accepted,
        addressed(body, "chromatin-failures"),
    )


__all__ = [
    "ChromatinArchitectureFailure",
    "ChromatinArchitectureFailureClass",
    "ChromatinArchitectureFailureReport",
    "classify_chromatin_architecture_failures",
]
