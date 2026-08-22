"""Record-level evaluation for the D07 C05-C08 public fixture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .methylation_frontier_adapters import (
    MethylationFrontierAdapterResult,
    execute_methylation_frontier_record,
)
from .methylation_frontier_public_data import (
    MethylationFrontierFixture,
    MethylationFrontierState,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class MethylationFrontierRecordEvaluation:
    record_id: str
    role: str
    expected_state: MethylationFrontierState
    observed_state: MethylationFrontierState
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    state_match: bool
    issue_match: bool
    accepted: bool
    adapter: MethylationFrontierAdapterResult
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
class MethylationFrontierEvaluation:
    fixture_id: str
    records: tuple[MethylationFrontierRecordEvaluation, ...]
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
    def results(self) -> tuple[MethylationFrontierAdapterResult, ...]:
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


def evaluate_methylation_frontier_fixture(
    fixture: MethylationFrontierFixture,
) -> MethylationFrontierEvaluation:
    """Execute every positive and control record and compare expected paths."""

    evaluations: list[MethylationFrontierRecordEvaluation] = []
    for record in fixture.records:
        result = execute_methylation_frontier_record(record)
        state_match = result.state is record.expected_state
        issue_match = set(record.expected_issue_codes) <= set(result.issue_codes)
        evaluations.append(
            MethylationFrontierRecordEvaluation(
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
    return MethylationFrontierEvaluation(
        fixture_id=fixture.fixture_id,
        records=items,
        positive_count=sum(item.role == "positive" for item in items),
        control_count=sum(item.role == "control" for item in items),
        state_match_count=sum(item.state_match for item in items),
        issue_match_count=sum(item.issue_match for item in items),
        accepted=all(item.accepted for item in items),
    )


__all__ = [
    "MethylationFrontierEvaluation",
    "MethylationFrontierRecordEvaluation",
    "evaluate_methylation_frontier_fixture",
]
