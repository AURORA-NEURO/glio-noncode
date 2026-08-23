"""Deterministic replay checks for the composed specimen evaluator."""

from __future__ import annotations

from dataclasses import dataclass

from .specimen_architecture_contracts import (
    SpecimenArchitectureEvaluation,
    SpecimenArchitectureFixture,
    addressed,
)
from .specimen_architecture_operations import evaluate_specimen_architecture_fixture


@dataclass(frozen=True, slots=True)
class SpecimenArchitectureReplayReport:
    fixture_id: str
    first_address: str
    second_address: str
    matching_receipts: bool
    matching_checks: bool
    accepted: bool
    content_address: str


def replay_specimen_architecture_fixture(
    fixture: SpecimenArchitectureFixture,
    baseline: SpecimenArchitectureEvaluation | None = None,
) -> SpecimenArchitectureReplayReport:
    """Run the fixture twice and compare only stable receipt projections."""

    first = baseline or evaluate_specimen_architecture_fixture(fixture)
    second = evaluate_specimen_architecture_fixture(fixture)

    def receipt_projection(evaluation: SpecimenArchitectureEvaluation) -> tuple[object, ...]:
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

    def check_projection(evaluation: SpecimenArchitectureEvaluation) -> tuple[object, ...]:
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
    return SpecimenArchitectureReplayReport(
        fixture.fixture_id,
        first.content_address,
        second.content_address,
        matching_receipts,
        matching_checks,
        accepted,
        addressed(body, "specimen-replay"),
    )


__all__ = ["SpecimenArchitectureReplayReport", "replay_specimen_architecture_fixture"]
