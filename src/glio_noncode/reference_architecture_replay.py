"""Deterministic replay checks for D04 architecture evaluation."""

from __future__ import annotations

from dataclasses import dataclass

from .reference_architecture_contracts import (
    ReferenceArchitectureEvaluation,
    ReferenceArchitectureFixture,
    addressed,
)
from .reference_architecture_operations import evaluate_reference_architecture_fixture
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class ReferenceArchitectureReplayReport:
    fixture_id: str
    first_address: str
    second_address: str
    matching_receipts: bool
    matching_checks: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, object]:
        return jsonable(self)


def replay_reference_architecture_fixture(
    fixture: ReferenceArchitectureFixture, baseline: ReferenceArchitectureEvaluation | None = None
) -> ReferenceArchitectureReplayReport:
    first = baseline or evaluate_reference_architecture_fixture(fixture)
    second = evaluate_reference_architecture_fixture(fixture)

    def receipt_projection(evaluation: ReferenceArchitectureEvaluation) -> tuple[object, ...]:
        return tuple(
            (
                item.case_id,
                item.observed_result_state,
                item.observed_issue_codes,
                dict(item.observed_counts),
                item.output_address,
            )
            for item in evaluation.receipts
        )

    def check_projection(evaluation: ReferenceArchitectureEvaluation) -> tuple[object, ...]:
        return tuple((item.check_id, item.passed) for item in evaluation.checks)

    matching_receipts = receipt_projection(first) == receipt_projection(second)
    matching_checks = check_projection(first) == check_projection(second)
    accepted = (
        matching_receipts and matching_checks and first.content_address == second.content_address
    )
    body = {
        "fixture_id": fixture.fixture_id,
        "first_address": first.content_address,
        "second_address": second.content_address,
        "matching_receipts": matching_receipts,
        "matching_checks": matching_checks,
        "accepted": accepted,
    }
    return ReferenceArchitectureReplayReport(
        fixture.fixture_id,
        first.content_address,
        second.content_address,
        matching_receipts,
        matching_checks,
        accepted,
        addressed(body, "reference-replay"),
    )


__all__ = ["ReferenceArchitectureReplayReport", "replay_reference_architecture_fixture"]
