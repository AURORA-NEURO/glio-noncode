"""Fixture evaluation and expected-state reconciliation for C01-C04."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_context_frontier_adapters import (
    ChromatinContextFrontierAdapterResult,
    execute_chromatin_context_frontier_record,
)
from .chromatin_context_frontier_public_data import (
    ChromatinContextFrontierFixture,
    ChromatinContextFrontierRecord,
)
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierEvaluationRow:
    record: ChromatinContextFrontierRecord
    adapter: ChromatinContextFrontierAdapterResult
    state_matches: bool
    issue_floor_matches: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.record.record_id or not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {"record": self.record.content_address, "adapter": self.adapter.content_address}
                ),
            )

    @property
    def record_id(self) -> str:
        return self.record.record_id

    @property
    def role(self) -> str:
        return self.record.role.value

    @property
    def operation(self) -> str:
        return self.record.operation.value

    @property
    def observed_state(self) -> str:
        return self.adapter.state

    @property
    def observed_issue_codes(self) -> tuple[str, ...]:
        return self.adapter.issue_codes

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "role": self.role,
            "operation": self.operation,
            "expected_state": self.record.expected_state.value,
            "observed_state": self.observed_state,
            "expected_issue_codes": list(self.record.expected_issue_codes),
            "observed_issue_codes": list(self.observed_issue_codes),
            "state_matches": self.state_matches,
            "issue_floor_matches": self.issue_floor_matches,
            "adapter": self.adapter.to_dict(),
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierEvaluation:
    fixture_id: str
    records: tuple[ChromatinContextFrontierEvaluationRow, ...]
    accepted: bool
    state_match_count: int
    issue_match_count: int
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.fixture_id or not self.records:
            raise ValidationError("context evaluation is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def positive_rows(self) -> tuple[ChromatinContextFrontierEvaluationRow, ...]:
        return tuple(item for item in self.records if item.role == "positive")

    @property
    def control_rows(self) -> tuple[ChromatinContextFrontierEvaluationRow, ...]:
        return tuple(item for item in self.records if item.role == "control")

    def by_operation(self, operation: str) -> tuple[ChromatinContextFrontierEvaluationRow, ...]:
        return tuple(item for item in self.records if item.operation == operation)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "records": [item.to_dict() for item in self.records],
            "accepted": self.accepted,
            "state_match_count": self.state_match_count,
            "issue_match_count": self.issue_match_count,
            "content_address": self.content_address,
        }


def evaluate_chromatin_context_frontier_fixture(
    fixture: ChromatinContextFrontierFixture,
) -> ChromatinContextFrontierEvaluation:
    rows: list[ChromatinContextFrontierEvaluationRow] = []
    for record in fixture.records:
        adapter = execute_chromatin_context_frontier_record(record)
        expected = record.expected_state.value
        state_matches = adapter.state == expected
        expected_codes = set(record.expected_issue_codes)
        observed_codes = set(adapter.issue_codes)
        issue_floor_matches = expected_codes.issubset(observed_codes)
        rows.append(
            ChromatinContextFrontierEvaluationRow(
                record, adapter, state_matches, issue_floor_matches
            )
        )
    state_match_count = sum(item.state_matches for item in rows)
    issue_match_count = sum(item.issue_floor_matches for item in rows)
    accepted = len(rows) == 16 and state_match_count == len(rows) and issue_match_count == len(rows)
    return ChromatinContextFrontierEvaluation(
        fixture.fixture_id,
        tuple(rows),
        accepted,
        state_match_count,
        issue_match_count,
    )


__all__ = [
    "ChromatinContextFrontierEvaluation",
    "ChromatinContextFrontierEvaluationRow",
    "evaluate_chromatin_context_frontier_fixture",
]
