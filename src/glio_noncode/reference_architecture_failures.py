"""Failure taxonomy for reference architecture release attempts."""

from __future__ import annotations

from dataclasses import dataclass

from .reference_architecture_contracts import (
    ReferenceArchitectureEvaluation,
    ReferenceArchitectureState,
    addressed,
)


@dataclass(frozen=True, slots=True)
class ReferenceArchitectureFailure:
    failure_id: str
    case_id: str
    category: str
    severity: str
    disposition: str
    detail: str
    content_address: str


@dataclass(frozen=True, slots=True)
class ReferenceArchitectureFailureReport:
    fixture_id: str
    failures: tuple[ReferenceArchitectureFailure, ...]
    release_blocked: bool
    content_address: str


def classify_reference_architecture_failures(
    evaluation: ReferenceArchitectureEvaluation,
) -> ReferenceArchitectureFailureReport:
    failures: list[ReferenceArchitectureFailure] = []
    for receipt in evaluation.receipts:
        if receipt.passed:
            continue
        category = (
            "positive_contract_mismatch"
            if receipt.expected_state is ReferenceArchitectureState.ACCEPTED
            else "control_policy_mismatch"
        )
        body = {
            "case_id": receipt.case_id,
            "category": category,
            "observed_result_state": receipt.observed_result_state,
        }
        failures.append(
            ReferenceArchitectureFailure(
                f"failure:{receipt.case_id}",
                receipt.case_id,
                category,
                "high",
                "block_release",
                "expected and observed reference receipt fields differ",
                addressed(body, "reference-failure"),
            )
        )
    return ReferenceArchitectureFailureReport(
        evaluation.fixture_id,
        tuple(failures),
        bool(failures),
        addressed(
            {"fixture_id": evaluation.fixture_id, "failures": failures}, "reference-failure-report"
        ),
    )


__all__ = [
    "ReferenceArchitectureFailure",
    "ReferenceArchitectureFailureReport",
    "classify_reference_architecture_failures",
]
