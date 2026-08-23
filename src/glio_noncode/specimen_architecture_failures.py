"""Failure taxonomy and conservative release disposition."""

from __future__ import annotations

from dataclasses import dataclass

from .specimen_architecture_contracts import (
    SpecimenArchitectureEvaluation,
    SpecimenArchitectureState,
    addressed,
)


@dataclass(frozen=True, slots=True)
class SpecimenArchitectureFailure:
    failure_id: str
    case_id: str
    category: str
    severity: str
    disposition: str
    detail: str
    content_address: str


@dataclass(frozen=True, slots=True)
class SpecimenArchitectureFailureReport:
    fixture_id: str
    failures: tuple[SpecimenArchitectureFailure, ...]
    release_blocked: bool
    content_address: str


def classify_specimen_architecture_failures(
    evaluation: SpecimenArchitectureEvaluation,
) -> SpecimenArchitectureFailureReport:
    """Classify failed receipts while retaining expected controls as non-failures."""

    failures: list[SpecimenArchitectureFailure] = []
    for receipt in evaluation.receipts:
        if receipt.passed:
            continue
        category = (
            "contract_mismatch"
            if receipt.expected_state is SpecimenArchitectureState.ACCEPTED
            else "control_policy_mismatch"
        )
        body = {
            "case_id": receipt.case_id,
            "category": category,
            "observed": receipt.observed_result_state,
        }
        failures.append(
            SpecimenArchitectureFailure(
                f"failure:{receipt.case_id}",
                receipt.case_id,
                category,
                "high",
                "block_release",
                "expected and observed receipt fields differ",
                addressed(body, "specimen-failure"),
            )
        )
    return SpecimenArchitectureFailureReport(
        evaluation.fixture_id,
        tuple(failures),
        bool(failures),
        addressed(
            {"fixture_id": evaluation.fixture_id, "failures": failures}, "specimen-failure-report"
        ),
    )


__all__ = [
    "SpecimenArchitectureFailure",
    "SpecimenArchitectureFailureReport",
    "classify_specimen_architecture_failures",
]
