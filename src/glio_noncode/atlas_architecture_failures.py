"""Failure taxonomy for D05 atlas release attempts."""

from __future__ import annotations

from dataclasses import dataclass

from .atlas_architecture_contracts import (
    AtlasArchitectureEvaluation,
    AtlasArchitectureState,
    addressed,
)


@dataclass(frozen=True, slots=True)
class AtlasArchitectureFailure:
    failure_id: str
    case_id: str
    category: str
    severity: str
    disposition: str
    detail: str
    content_address: str


@dataclass(frozen=True, slots=True)
class AtlasArchitectureFailureReport:
    fixture_id: str
    failures: tuple[AtlasArchitectureFailure, ...]
    release_blocked: bool
    content_address: str

    def to_dict(self) -> dict[str, object]:
        from .serialization import jsonable

        return jsonable(self)


def classify_atlas_architecture_failures(
    evaluation: AtlasArchitectureEvaluation,
) -> AtlasArchitectureFailureReport:
    failures: list[AtlasArchitectureFailure] = []
    for receipt in evaluation.receipts:
        if receipt.passed:
            continue
        category = (
            "positive_contract_mismatch"
            if receipt.expected_state is AtlasArchitectureState.ACCEPTED
            else "control_policy_mismatch"
        )
        body = {
            "case_id": receipt.case_id,
            "category": category,
            "observed_result_state": receipt.observed_result_state,
        }
        failures.append(
            AtlasArchitectureFailure(
                f"failure:{receipt.case_id}",
                receipt.case_id,
                category,
                "high",
                "block_release",
                "expected and observed atlas receipt fields differ",
                addressed(body, "atlas-failure"),
            )
        )
    body = {"fixture_id": evaluation.fixture_id, "failures": failures}
    return AtlasArchitectureFailureReport(
        evaluation.fixture_id,
        tuple(failures),
        bool(failures),
        addressed(body, "atlas-failure-report"),
    )


__all__ = [
    "AtlasArchitectureFailure",
    "AtlasArchitectureFailureReport",
    "classify_atlas_architecture_failures",
]
