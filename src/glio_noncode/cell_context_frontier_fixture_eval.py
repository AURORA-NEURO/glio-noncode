"""Fixture evaluation for Domain 08 C01-C04."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_frontier_adapters import (
    CellContextFrontierAdapterResult,
    execute_cell_context_frontier_record,
)
from .cell_context_frontier_public_data import CellContextFrontierFixture, CellContextFrontierRecord
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextFrontierEvaluationRow:
    record: CellContextFrontierRecord
    adapter: CellContextFrontierAdapterResult
    state_matches: bool
    issue_floor_matches: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.record.record_id:
            raise ValidationError("context evaluation record ID is required")
        if not self.content_address:
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
class CellContextFrontierEvaluation:
    fixture_id: str
    records: tuple[CellContextFrontierEvaluationRow, ...]
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
    def positive_rows(self) -> tuple[CellContextFrontierEvaluationRow, ...]:
        return tuple(item for item in self.records if item.role == "positive")

    @property
    def control_rows(self) -> tuple[CellContextFrontierEvaluationRow, ...]:
        return tuple(item for item in self.records if item.role == "control")

    def by_operation(self, operation: str) -> tuple[CellContextFrontierEvaluationRow, ...]:
        return tuple(item for item in self.records if item.operation == operation)

    def by_state(self, state: str) -> tuple[CellContextFrontierEvaluationRow, ...]:
        return tuple(item for item in self.records if item.observed_state == state)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "records": [item.to_dict() for item in self.records],
            "accepted": self.accepted,
            "state_match_count": self.state_match_count,
            "issue_match_count": self.issue_match_count,
            "content_address": self.content_address,
        }


def evaluate_cell_context_frontier_fixture(
    fixture: CellContextFrontierFixture,
) -> CellContextFrontierEvaluation:
    rows: list[CellContextFrontierEvaluationRow] = []
    for record in fixture.records:
        adapter = execute_cell_context_frontier_record(record)
        state_matches = adapter.state == record.expected_state.value
        issue_floor_matches = set(record.expected_issue_codes).issubset(adapter.issue_codes)
        rows.append(
            CellContextFrontierEvaluationRow(record, adapter, state_matches, issue_floor_matches)
        )
    state_match_count = sum(item.state_matches for item in rows)
    issue_match_count = sum(item.issue_floor_matches for item in rows)
    accepted = len(rows) == 16 and state_match_count == 16 and issue_match_count == 16
    return CellContextFrontierEvaluation(
        fixture.fixture_id, tuple(rows), accepted, state_match_count, issue_match_count
    )


__all__ = [
    "CellContextFrontierEvaluation",
    "CellContextFrontierEvaluationRow",
    "evaluate_cell_context_frontier_fixture",
]
