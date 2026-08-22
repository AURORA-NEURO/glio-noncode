"""Fixture execution and expectation reconciliation for Domain 08 C09-C12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_alpha_frontier_adapters import (
    CellContextAlphaFrontierAdapterResult,
    execute_cell_context_alpha_frontier_record,
)
from .cell_context_alpha_frontier_public_data import (
    CellContextAlphaFrontierFixture,
    CellContextAlphaFrontierRecord,
    default_cell_context_alpha_frontier_fixture,
)
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierEvaluationRow:
    record: CellContextAlphaFrontierRecord
    adapter: CellContextAlphaFrontierAdapterResult
    state_matches: bool
    issue_floor_matches: bool
    content_address: str = ""

    def __post_init__(self) -> None:
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
class CellContextAlphaFrontierEvaluation:
    fixture_id: str
    records: tuple[CellContextAlphaFrontierEvaluationRow, ...]
    accepted: bool
    state_match_count: int
    issue_match_count: int
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.records:
            raise ValidationError("alpha evaluation is empty")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def positive_rows(self) -> tuple[CellContextAlphaFrontierEvaluationRow, ...]:
        return tuple(item for item in self.records if item.role == "positive")

    @property
    def control_rows(self) -> tuple[CellContextAlphaFrontierEvaluationRow, ...]:
        return tuple(item for item in self.records if item.role == "control")

    def by_operation(self, operation: str) -> tuple[CellContextAlphaFrontierEvaluationRow, ...]:
        return tuple(item for item in self.records if item.operation == operation)

    def by_state(self, state: str) -> tuple[CellContextAlphaFrontierEvaluationRow, ...]:
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


def evaluate_cell_context_alpha_frontier_fixture(
    fixture: CellContextAlphaFrontierFixture | None = None,
) -> CellContextAlphaFrontierEvaluation:
    fixture = fixture or default_cell_context_alpha_frontier_fixture()
    rows = []
    for record in fixture.records:
        adapter = execute_cell_context_alpha_frontier_record(record)
        rows.append(
            CellContextAlphaFrontierEvaluationRow(
                record,
                adapter,
                adapter.state == record.expected_state.value,
                set(record.expected_issue_codes).issubset(adapter.issue_codes),
            )
        )
    state_count = sum(item.state_matches for item in rows)
    issue_count = sum(item.issue_floor_matches for item in rows)
    return CellContextAlphaFrontierEvaluation(
        fixture.fixture_id,
        tuple(rows),
        len(rows) == 16 and state_count == 16 and issue_count == 16,
        state_count,
        issue_count,
    )


__all__ = [
    "CellContextAlphaFrontierEvaluation",
    "CellContextAlphaFrontierEvaluationRow",
    "evaluate_cell_context_alpha_frontier_fixture",
]
