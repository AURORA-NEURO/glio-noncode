"""Record-level evaluation for the C09-C12 public fixture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_regulation_frontier_adapters import (
    SequenceRegulationAdapterResult,
    execute_sequence_regulation_record,
)
from .sequence_regulation_frontier_public_data import (
    SequenceRegulationFixture,
    SequenceRegulationState,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceRegulationRecordEvaluation:
    record_id: str
    role: str
    expected_state: SequenceRegulationState
    observed_state: SequenceRegulationState
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    state_match: bool
    issue_match: bool
    accepted: bool
    adapter: SequenceRegulationAdapterResult
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.record_id:
            raise ValidationError("evaluation requires a record ID")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "record_id": self.record_id,
                        "role": self.role,
                        "expected_state": self.expected_state,
                        "observed_state": self.observed_state,
                        "expected_issue_codes": self.expected_issue_codes,
                        "observed_issue_codes": self.observed_issue_codes,
                        "state_match": self.state_match,
                        "issue_match": self.issue_match,
                        "accepted": self.accepted,
                        "adapter": self.adapter.content_address,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceRegulationEvaluation:
    fixture_id: str
    records: tuple[SequenceRegulationRecordEvaluation, ...]
    positive_count: int
    control_count: int
    state_match_count: int
    issue_match_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.records:
            raise ValidationError("evaluation requires records")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "fixture_id": self.fixture_id,
                        "records": self.records,
                        "positive_count": self.positive_count,
                        "control_count": self.control_count,
                        "state_match_count": self.state_match_count,
                        "issue_match_count": self.issue_match_count,
                        "accepted": self.accepted,
                    }
                ),
            )

    @property
    def failed_record_ids(self) -> tuple[str, ...]:
        return tuple(item.record_id for item in self.records if not item.accepted)

    @property
    def results(self) -> tuple[SequenceRegulationAdapterResult, ...]:
        return tuple(item.adapter for item in self.records)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "record_count": len(self.records),
            "positive_count": self.positive_count,
            "control_count": self.control_count,
            "state_match_count": self.state_match_count,
            "issue_match_count": self.issue_match_count,
            "failed_record_ids": list(self.failed_record_ids),
            "accepted": self.accepted,
            "records": [record.to_dict() for record in self.records],
            "content_address": self.content_address,
        }


def _expected_issue_match(expected: tuple[str, ...], observed: tuple[str, ...]) -> bool:
    return set(expected) <= set(observed)


def evaluate_sequence_regulation_fixture(
    fixture: SequenceRegulationFixture,
) -> SequenceRegulationEvaluation:
    """Execute and compare every fixture record, including controls."""

    evaluations: list[SequenceRegulationRecordEvaluation] = []
    for record in fixture.records:
        result = execute_sequence_regulation_record(record)
        state_match = result.state is record.expected_state
        issue_match = _expected_issue_match(record.expected_issue_codes, result.issue_codes)
        evaluations.append(
            SequenceRegulationRecordEvaluation(
                record_id=record.record_id,
                role=record.role.value,
                expected_state=record.expected_state,
                observed_state=result.state,
                expected_issue_codes=record.expected_issue_codes,
                observed_issue_codes=result.issue_codes,
                state_match=state_match,
                issue_match=issue_match,
                accepted=state_match and issue_match,
                adapter=result,
            )
        )
    items = tuple(evaluations)
    state_match_count = sum(item.state_match for item in items)
    issue_match_count = sum(item.issue_match for item in items)
    return SequenceRegulationEvaluation(
        fixture_id=fixture.fixture_id,
        records=items,
        positive_count=sum(item.role == "positive" for item in items),
        control_count=sum(item.role == "control" for item in items),
        state_match_count=state_match_count,
        issue_match_count=issue_match_count,
        accepted=all(item.accepted for item in items),
    )


__all__ = [
    "SequenceRegulationEvaluation",
    "SequenceRegulationRecordEvaluation",
    "evaluate_sequence_regulation_fixture",
]
