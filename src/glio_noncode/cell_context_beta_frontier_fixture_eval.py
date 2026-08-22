"""Fixture evaluation for Domain 08 C05-C08."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_beta_frontier_adapters import (
    CellContextBetaFrontierAdapterResult,
    execute_cell_context_beta_frontier_record,
)
from .cell_context_beta_frontier_public_data import (
    CellContextBetaFrontierFixture,
    CellContextBetaFrontierRecord,
    default_cell_context_beta_frontier_fixture,
)
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierEvaluationRow:
    record: CellContextBetaFrontierRecord
    adapter: CellContextBetaFrontierAdapterResult
    state_matches: bool
    issue_floor_matches: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.record.record_id:
            raise ValidationError("beta evaluation record ID is required")
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
class CellContextBetaFrontierEvaluation:
    fixture_id: str
    records: tuple[CellContextBetaFrontierEvaluationRow, ...]
    accepted: bool
    state_match_count: int
    issue_match_count: int
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.fixture_id or not self.records:
            raise ValidationError("beta evaluation is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def positive_rows(self) -> tuple[CellContextBetaFrontierEvaluationRow, ...]:
        return tuple(item for item in self.records if item.role == "positive")

    @property
    def control_rows(self) -> tuple[CellContextBetaFrontierEvaluationRow, ...]:
        return tuple(item for item in self.records if item.role == "control")

    def by_operation(self, operation: str) -> tuple[CellContextBetaFrontierEvaluationRow, ...]:
        return tuple(item for item in self.records if item.operation == operation)

    def by_state(self, state: str) -> tuple[CellContextBetaFrontierEvaluationRow, ...]:
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


def evaluate_cell_context_beta_frontier_fixture(
    fixture: CellContextBetaFrontierFixture | None = None,
) -> CellContextBetaFrontierEvaluation:
    fixture = fixture or default_cell_context_beta_frontier_fixture()
    rows: list[CellContextBetaFrontierEvaluationRow] = []
    for record in fixture.records:
        adapter = execute_cell_context_beta_frontier_record(record)
        rows.append(
            CellContextBetaFrontierEvaluationRow(
                record,
                adapter,
                adapter.state == record.expected_state.value,
                set(record.expected_issue_codes).issubset(adapter.issue_codes),
            )
        )
    state_matches = sum(item.state_matches for item in rows)
    issue_matches = sum(item.issue_floor_matches for item in rows)
    return CellContextBetaFrontierEvaluation(
        fixture.fixture_id,
        tuple(rows),
        len(rows) == 16 and state_matches == 16 and issue_matches == 16,
        state_matches,
        issue_matches,
    )


__all__ = [
    "CellContextBetaFrontierEvaluation",
    "CellContextBetaFrontierEvaluationRow",
    "evaluate_cell_context_beta_frontier_fixture",
]
