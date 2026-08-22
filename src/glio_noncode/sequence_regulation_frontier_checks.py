"""Cross-object invariants for the C09-C12 release."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_regulation_frontier_fixture_eval import SequenceRegulationEvaluation
from .sequence_regulation_frontier_public_data import (
    SequenceRegulationFixture,
    SequenceRegulationOperation,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceRegulationInvariant:
    invariant_id: str
    passed: bool
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.invariant_id or not self.detail:
            raise ValidationError("invariant is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceRegulationInvariantReport:
    invariants: tuple[SequenceRegulationInvariant, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.invariants:
            raise ValidationError("invariant report requires invariants")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def run_sequence_regulation_invariants(
    fixture: SequenceRegulationFixture,
    evaluation: SequenceRegulationEvaluation,
) -> SequenceRegulationInvariantReport:
    expected_operations = set(SequenceRegulationOperation)
    seen_operations = {item.adapter.operation for item in evaluation.records}
    checks = (
        SequenceRegulationInvariant(
            "record_count",
            len(evaluation.records) == len(fixture.records),
            "evaluation covers every fixture record",
        ),
        SequenceRegulationInvariant(
            "positive_count", evaluation.positive_count == 4, "positive count is four"
        ),
        SequenceRegulationInvariant(
            "control_count", evaluation.control_count == 12, "control count is twelve"
        ),
        SequenceRegulationInvariant(
            "operation_coverage",
            seen_operations == expected_operations,
            "all four operations are present",
        ),
        SequenceRegulationInvariant(
            "unique_records",
            len({item.record_id for item in evaluation.records}) == len(evaluation.records),
            "record IDs are unique",
        ),
        SequenceRegulationInvariant(
            "receipt_coverage",
            all(item.adapter.content_address.startswith("sha256:") for item in evaluation.records),
            "every result has a receipt",
        ),
        SequenceRegulationInvariant(
            "state_coverage",
            evaluation.state_match_count == len(evaluation.records),
            "states match expected controls",
        ),
        SequenceRegulationInvariant(
            "issue_coverage",
            evaluation.issue_match_count == len(evaluation.records),
            "issue paths match expected controls",
        ),
    )
    return SequenceRegulationInvariantReport(checks, all(check.passed for check in checks))


__all__ = [
    "SequenceRegulationInvariant",
    "SequenceRegulationInvariantReport",
    "run_sequence_regulation_invariants",
]
