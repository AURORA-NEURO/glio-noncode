"""Deterministic replay of D06 aggregate evaluation."""

from __future__ import annotations

from dataclasses import dataclass

from .sequence_architecture_contracts import (
    SequenceArchitectureEvaluation,
    SequenceArchitectureFixture,
    addressed,
)
from .sequence_architecture_operations import evaluate_sequence_architecture_fixture


@dataclass(frozen=True, slots=True)
class SequenceArchitectureReplayReport:
    fixture_id: str
    first_address: str
    second_address: str
    matching_receipts: bool
    matching_checks: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, object]:
        return {field: getattr(self, field) for field in self.__dataclass_fields__}


def replay_sequence_architecture_fixture(
    fixture: SequenceArchitectureFixture, baseline: SequenceArchitectureEvaluation | None = None
) -> SequenceArchitectureReplayReport:
    first = baseline or evaluate_sequence_architecture_fixture(fixture)
    second = evaluate_sequence_architecture_fixture(fixture)
    receipts = _receipt_projection(first) == _receipt_projection(second)
    checks = _check_projection(first) == _check_projection(second)
    accepted = receipts and checks and first.content_address == second.content_address
    body = {
        "fixture_id": fixture.fixture_id,
        "first_address": first.content_address,
        "second_address": second.content_address,
        "matching_receipts": receipts,
        "matching_checks": checks,
        "accepted": accepted,
    }
    return SequenceArchitectureReplayReport(
        fixture_id=fixture.fixture_id,
        first_address=first.content_address,
        second_address=second.content_address,
        matching_receipts=receipts,
        matching_checks=checks,
        accepted=accepted,
        content_address=addressed(body, "sequence-replay"),
    )


def _receipt_projection(evaluation: SequenceArchitectureEvaluation) -> tuple[object, ...]:
    return tuple(
        (
            item.case_id,
            item.observed_state,
            item.observed_result_state,
            item.observed_issue_codes,
            item.observed_counts,
            item.output_address,
        )
        for item in evaluation.receipts
    )


def _check_projection(evaluation: SequenceArchitectureEvaluation) -> tuple[object, ...]:
    return tuple((item.check_id, item.passed) for item in evaluation.checks)


__all__ = ["SequenceArchitectureReplayReport", "replay_sequence_architecture_fixture"]
